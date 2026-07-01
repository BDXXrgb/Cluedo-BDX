from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from pathlib import Path
from datetime import datetime
import json
import base64
import secrets
from app.db import engine, async_session, Base
from app.models import User, Match, GameEvent
from app.schemas import RegisterIn, LoginIn, TokenOut
from app.auth import hash_password, verify_password, create_access_token, decode_token, get_user_by_username
from app.game import CluedoGame, SUSPECTS, WEAPONS, ROOMS, BOARD_W, BOARD_H, ROOM_AREAS, ROOM_PORTALS, is_room, neighbors

app = FastAPI(title="BDX Cluedo en Ligne")
app.mount("/static", StaticFiles(directory="static"), name="static")

game = CluedoGame()
connections = {}
tokens = {}

async def get_session():
    async with async_session() as session:
        yield session

@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

@app.get("/")
async def home():
    return HTMLResponse(Path("static/index.html").read_text(encoding="utf-8"))

@app.post("/api/register", response_model=TokenOut)
async def register(data: RegisterIn, session: AsyncSession = Depends(get_session)):
    if await get_user_by_username(session, data.username):
        raise HTTPException(400, "Username already exists")
    user = User(username=data.username, password_hash=hash_password(data.password))
    session.add(user)
    await session.commit()
    token = create_access_token({"sub": user.username})
    tokens[token] = user.username
    return {"access_token": token, "token_type": "bearer"}

@app.post("/api/login", response_model=TokenOut)
async def login(data: LoginIn, session: AsyncSession = Depends(get_session)):
    user = await get_user_by_username(session, data.username)
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(401, "Bad credentials")
    token = create_access_token({"sub": user.username})
    tokens[token] = user.username
    return {"access_token": token, "token_type": "bearer"}

@app.get("/api/leaderboard")
async def leaderboard(session: AsyncSession = Depends(get_session)):
    res = await session.execute(select(User).order_by(desc(User.wins), User.losses, User.username).limit(50))
    users = res.scalars().all()
    return [{"username": u.username, "wins": u.wins, "losses": u.losses} for u in users]

@app.get("/api/matches")
async def matches(session: AsyncSession = Depends(get_session)):
    res = await session.execute(select(Match).order_by(desc(Match.started_at)).limit(20))
    rows = res.scalars().all()
    return [{"id": m.id, "winner": m.winner_username, "solution": m.solution_json, "started_at": m.started_at.isoformat(), "ended_at": m.ended_at.isoformat() if m.ended_at else None} for m in rows]

async def save_event(session, match_id, username, event_type, payload):
    session.add(GameEvent(match_id=match_id, username=username, event_type=event_type, payload_json=json.dumps(payload, ensure_ascii=False)))
    await session.commit()

async def broadcast(message: dict):
    data = json.dumps(message)
    dead = []
    for pid, ws in connections.items():
        try:
            await ws.send_text(data)
        except Exception:
            dead.append(pid)
    for pid in dead:
        connections.pop(pid, None)
        game.remove_player(pid)

async def send_to(pid: str, message: dict):
    ws = connections.get(pid)
    if ws:
        await ws.send_text(json.dumps(message))

def parse_token_from_ws_url(url: str):
    if "?token=" in url:
        return url.split("?token=")[-1]
    return None

async def authenticate_ws(websocket: WebSocket):
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=1008)
        return None
    try:
        payload = decode_token(token)
        return payload.get("sub")
    except Exception:
        await websocket.close(code=1008)
        return None

@app.websocket("/ws/{player_id}")
async def ws_endpoint(websocket: WebSocket, player_id: str):
    username = await authenticate_ws(websocket)
    if not username:
        return
    await websocket.accept()
    connections[player_id] = websocket
    player = game.add_player(player_id, username, is_bot=False)

    await send_to(player_id, {"type": "init", "player_id": player_id, "state": game.public_state()})
    await broadcast({"type": "state", "state": game.public_state()})

    try:
        while True:
            raw = await websocket.receive_text()
            msg = json.loads(raw)
            typ = msg.get("type")

            if typ == "set_name":
                new_name = str(msg.get("name", username))[:24]
                game.players[player_id].name = new_name
                game.history.append(f"{new_name} rejoint la table.")
                await broadcast({"type": "state", "state": game.public_state()})

            elif typ == "set_character":
                ch = msg.get("character")
                if ch in SUSPECTS:
                    game.players[player_id].character = ch
                    game.history.append(f"{game.players[player_id].name} choisit {ch}.")
                    await broadcast({"type": "state", "state": game.public_state()})

            elif typ == "start_game":
                if not game.started and len(game.players) >= 2:
                    game.setup()
                    async with async_session() as session:
                        m = Match(solution_json=json.dumps(game.envelope, ensure_ascii=False))
                        session.add(m)
                        await session.commit()
                        await session.refresh(m)
                        game.match_id = m.id
                    await broadcast({"type": "state", "state": game.public_state()})

            elif typ == "chat":
                text = str(msg.get("text", ""))[:200]
                name = game.players[player_id].name
                game.history.append(f"{name}: {text}")
                async with async_session() as session:
                    if game.match_id:
                        await save_event(session, game.match_id, name, "chat", {"text": text})
                await broadcast({"type": "chat", "from": name, "text": text})

            elif typ == "roll":
                if game.current_player_id() == player_id:
                    dice = int(msg.get("dice", 0))
                    if 1 <= dice <= 6:
                        game.start_turn(player_id, dice)
                        await broadcast({"type": "state", "state": game.public_state()})

            elif typ == "move":
                if game.current_player_id() == player_id:
                    nx = int(msg.get("x", -1))
                    ny = int(msg.get("y", -1))
                    if game.move_step(player_id, nx, ny):
                        await broadcast({"type": "state", "state": game.public_state()})

            elif typ == "secret_passage":
                if game.current_player_id() == player_id and game.use_secret_passage(player_id):
                    await broadcast({"type": "state", "state": game.public_state()})

            elif typ == "suggestion":
                if game.current_player_id() == player_id:
                    suspect = msg.get("suspect")
                    weapon = msg.get("weapon")
                    room = msg.get("room")
                    s = game.suggest(player_id, suspect, weapon, room)
                    if s:
                        shown = False
                        players = list(game.turn_order)
                        start = players.index(player_id)
                        for i in range(1, len(players)):
                            pid = players[(start + i) % len(players)]
                            p = game.players[pid]
                            for card in p.hand:
                                if card in [suspect, weapon, room]:
                                    game.last_suggestion["shown_by"] = pid
                                    game.last_suggestion["shown_card"] = card
                                    game.notes[player_id]["seen"].append(card)
                                    game.notes[pid]["confirmed"].append(card)
                                    await send_to(player_id, {"type": "suggestion_result", "card": card, "from": p.name})
                                    await send_to(pid, {"type": "reveal_notice", "to": game.players[player_id].name, "card": card})
                                    shown = True
                                    break
                            if shown:
                                break
                        if not shown:
                            await send_to(player_id, {"type": "suggestion_result", "card": None, "from": None})
                        await broadcast({"type": "state", "state": game.public_state()})

            elif typ == "accusation":
                if game.current_player_id() == player_id:
                    suspect = msg.get("suspect")
                    weapon = msg.get("weapon")
                    room = msg.get("room")
                    correct = game.check_accusation(suspect, weapon, room)
                    name = game.players[player_id].name
                    async with async_session() as session:
                        user = await get_user_by_username(session, username)
                        if user:
                            if correct:
                                user.wins += 1
                            else:
                                user.losses += 1
                            await session.commit()
                    if correct:
                        game.winner = name
                        game.started = False
                        game.history.append(f"{name} gagne la partie.")
                        async with async_session() as session:
                            if game.match_id:
                                match = await session.get(Match, game.match_id)
                                if match:
                                    match.winner_username = username
                                    match.ended_at = datetime.utcnow()
                                    await session.commit()
                        await broadcast({"type": "game_over", "winner": name, "solution": game.envelope})
                    else:
                        game.players[player_id].alive = False
                        game.history.append(f"{name} a fait une mauvaise accusation.")
                        await send_to(player_id, {"type": "accusation_result", "correct": False, "solution": game.envelope})
                        await broadcast({"type": "state", "state": game.public_state()})

            elif typ == "end_turn":
                if game.current_player_id() == player_id:
                    game.next_turn()
                    await broadcast({"type": "state", "state": game.public_state()})

            elif typ == "bot_fill":
                await broadcast({"type": "state", "state": game.public_state()})

    except WebSocketDisconnect:
        connections.pop(player_id, None)
        game.remove_player(player_id)
        await broadcast({"type": "state", "state": game.public_state()})

@app.get("/api/debug/state")
async def debug_state():
    return JSONResponse(game.public_state())