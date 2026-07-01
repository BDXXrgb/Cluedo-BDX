import random
from dataclasses import dataclass, field

SUSPECTS = ["Miss Scarlet", "Colonel Mustard", "Mrs. White", "Mr. Green", "Mrs. Peacock", "Professor Plum"]
WEAPONS = ["Candlestick", "Dagger", "Lead Pipe", "Pistol", "Rope", "Wrench"]
ROOMS = ["Kitchen", "Ballroom", "Conservatory", "Dining Room", "Billiard Room", "Library", "Lounge", "Hall", "Study"]

SECRET_PASSAGES = {"Kitchen": "Study", "Study": "Kitchen", "Conservatory": "Lounge", "Lounge": "Conservatory"}

BOARD_W = 24
BOARD_H = 24

ROOM_AREAS = {
    "Kitchen": (0, 0, 6, 6),
    "Ballroom": (9, 0, 6, 7),
    "Conservatory": (18, 0, 6, 6),
    "Dining Room": (0, 9, 7, 6),
    "Billiard Room": (9, 9, 6, 6),
    "Library": (18, 9, 6, 6),
    "Lounge": (0, 18, 6, 6),
    "Hall": (9, 18, 6, 6),
    "Study": (18, 18, 6, 6),
}

ROOM_PORTALS = {
    "Kitchen": [(6, 2)],
    "Ballroom": [(11, 7), (13, 7)],
    "Conservatory": [(18, 2)],
    "Dining Room": [(6, 11)],
    "Billiard Room": [(11, 9), (13, 9)],
    "Library": [(18, 11)],
    "Lounge": [(6, 20)],
    "Hall": [(11, 18), (13, 18)],
    "Study": [(18, 20)],
}

START_POSITIONS = {
    "Miss Scarlet": (11, 23),
    "Colonel Mustard": (0, 12),
    "Mrs. White": (12, 0),
    "Mr. Green": (23, 12),
    "Mrs. Peacock": (23, 10),
    "Professor Plum": (0, 10),
}

@dataclass
class Player:
    pid: str
    name: str
    character: str | None = None
    x: int = 11
    y: int = 11
    alive: bool = True
    is_bot: bool = False
    hand: list[str] = field(default_factory=list)
    moves_left: int = 0
    in_room: str | None = None
    ready: bool = False

def is_room(x, y):
    for r, (rx, ry, rw, rh) in ROOM_AREAS.items():
        if rx <= x < rx + rw and ry <= y < ry + rh:
            return r
    return None

def is_walkable(x, y):
    return 0 <= x < BOARD_W and 0 <= y < BOARD_H and is_room(x, y) is None

def neighbors(x, y):
    out = []
    for dx, dy in [(1,0), (-1,0), (0,1), (0,-1)]:
        nx, ny = x + dx, y + dy
        if is_walkable(nx, ny):
            out.append((nx, ny))
    return out

class CluedoGame:
    def __init__(self):
        self.started = False
        self.turn_order = []
        self.turn_index = 0
        self.players = {}
        self.envelope = {}
        self.history = []
        self.notes = {}
        self.last_suggestion = None
        self.winner = None
        self.match_id = None

    def add_player(self, pid, name, is_bot=False):
        if pid not in self.players:
            self.players[pid] = Player(pid=pid, name=name, is_bot=is_bot)
            self.turn_order.append(pid)
            self.notes[pid] = {"seen": [], "confirmed": [], "cannot_have": {}}
        return self.players[pid]

    def remove_player(self, pid):
        self.players.pop(pid, None)
        self.notes.pop(pid, None)
        if pid in self.turn_order:
            idx = self.turn_order.index(pid)
            self.turn_order.remove(pid)
            if self.turn_index >= len(self.turn_order):
                self.turn_index = 0
            elif idx <= self.turn_index and self.turn_index > 0:
                self.turn_index -= 1

    def current_player_id(self):
        return self.turn_order[self.turn_index % len(self.turn_order)] if self.turn_order else None

    def current_player(self):
        pid = self.current_player_id()
        return self.players.get(pid) if pid else None

    def setup(self):
        self.envelope = {
            "suspect": random.choice(SUSPECTS),
            "weapon": random.choice(WEAPONS),
            "room": random.choice(ROOMS),
        }
        deck = SUSPECTS[:] + WEAPONS[:] + ROOMS[:]
        for card in self.envelope.values():
            deck.remove(card)
        random.shuffle(deck)
        for p in self.players.values():
            p.hand = []
            p.alive = True
            p.moves_left = 0
        i = 0
        while deck:
            pid = self.turn_order[i % len(self.turn_order)]
            self.players[pid].hand.append(deck.pop())
            i += 1
        for p in self.players.values():
            if p.character in START_POSITIONS:
                p.x, p.y = START_POSITIONS[p.character]
            else:
                p.x, p.y = 11, 11
            p.in_room = is_room(p.x, p.y)
        self.started = True
        self.turn_index = 0
        self.history.append("Partie lancée.")
        return self.envelope

    def public_state(self):
        return {
            "started": self.started,
            "turn_order": self.turn_order,
            "turn_index": self.turn_index,
            "current_player_id": self.current_player_id(),
            "players": {
                pid: {
                    "name": p.name,
                    "character": p.character,
                    "x": p.x,
                    "y": p.y,
                    "alive": p.alive,
                    "is_bot": p.is_bot,
                    "hand_size": len(p.hand),
                    "moves_left": p.moves_left,
                    "in_room": p.in_room,
                }
                for pid, p in self.players.items()
            },
            "history": self.history[-50:],
            "notes": self.notes,
            "winner": self.winner,
            "last_suggestion": self.last_suggestion,
            "rooms": ROOMS,
            "suspects": SUSPECTS,
            "weapons": WEAPONS,
            "secret_passages": SECRET_PASSAGES,
            "board_w": BOARD_W,
            "board_h": BOARD_H,
            "room_areas": ROOM_AREAS,
            "room_portals": ROOM_PORTALS,
        }

    def next_turn(self):
        if self.turn_order:
            self.turn_index = (self.turn_index + 1) % len(self.turn_order)
            self.history.append(f"Tour de {self.players[self.current_player_id()].name}.")

    def start_turn(self, pid, dice=0):
        p = self.players.get(pid)
        if p:
            p.moves_left = dice
            p.in_room = is_room(p.x, p.y)
            self.history.append(f"{p.name} commence son tour avec {dice} mouvements.")

    def move_step(self, pid, nx, ny):
        p = self.players.get(pid)
        if not p or p.moves_left <= 0:
            return False
        if (nx, ny) not in neighbors(p.x, p.y):
            return False
        occupied = any((op.x, op.y) == (nx, ny) and op.pid != pid and op.alive for op in self.players.values())
        if occupied:
            return False
        p.x, p.y = nx, ny
        p.moves_left -= 1
        p.in_room = is_room(nx, ny)
        if p.moves_left == 0:
            room = self.get_room_from_door(nx, ny)
            if room:
                p.x, p.y = ROOM_PORTALS[room][0]
                p.in_room = room
        self.history.append(f"{p.name} se déplace en ({nx},{ny}).")
        return True

    def get_room_from_door(self, x, y):
        for room, portals in ROOM_PORTALS.items():
            if (x, y) in portals:
                return room
        return None

    def use_secret_passage(self, pid):
        p = self.players.get(pid)
        if not p:
            return False
        room = p.in_room or is_room(p.x, p.y)
        if room in SECRET_PASSAGES:
            dest = SECRET_PASSAGES[room]
            px, py = ROOM_PORTALS[dest][0]
            p.x, p.y = px, py
            p.in_room = dest
            self.history.append(f"{p.name} utilise un passage secret vers {dest}.")
            return True
        return False

    def suggest(self, pid, suspect, weapon, room):
        p = self.players.get(pid)
        if not p:
            return None
        if p.in_room != room:
            return None
        self.last_suggestion = {"by": pid, "suspect": suspect, "weapon": weapon, "room": room, "shown_by": None, "shown_card": None}
        self.history.append(f"{p.name} suggère {suspect}, {weapon}, {room}.")
        return self.last_suggestion

    def check_accusation(self, suspect, weapon, room):
        return suspect == self.envelope.get("suspect") and weapon == self.envelope.get("weapon") and room == self.envelope.get("room")