let ws;
let token = localStorage.getItem('bdx_token') || '';
let playerId = crypto.randomUUID();
let currentState = null;

const stateEl = document.getElementById('state');
const chatEl = document.getElementById('chat');
const nameEl = document.getElementById('name');
const msgEl = document.getElementById('msg');
const roomEl = document.getElementById('room');
const suspectEl = document.getElementById('suspect');
const weaponEl = document.getElementById('weapon');
const characterEl = document.getElementById('character');
const boardEl = document.getElementById('board');

async function api(path, body) {
  const res = await fetch(path, {
    method: 'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify(body)
  });
  return await res.json();
}

document.getElementById('register').onclick = async () => {
  const u = document.getElementById('username').value;
  const p = document.getElementById('password').value;
  const data = await api('/api/register', {username:u, password:p});
  token = data.access_token;
  localStorage.setItem('bdx_token', token);
  document.getElementById('authstatus').textContent = 'Compte créé et connecté';
};

document.getElementById('login').onclick = async () => {
  const u = document.getElementById('username').value;
  const p = document.getElementById('password').value;
  const data = await api('/api/login', {username:u, password:p});
  token = data.access_token;
  localStorage.setItem('bdx_token', token);
  document.getElementById('authstatus').textContent = 'Connecté';
};

function renderBoard(state) {
  if (!state) return;
  const w = state.board_w, h = state.board_h;
  boardEl.style.gridTemplateColumns = `repeat(${w}, 22px)`;
  boardEl.innerHTML = '';
  const playerPositions = {};
  Object.entries(state.players || {}).forEach(([pid, p]) => {
    if (p.alive) {
      playerPositions[`${p.x},${p.y}`] = p.name[0].toUpperCase();
    }
  });
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      const div = document.createElement('div');
      div.className = 'cell';
      const room = Object.entries(state.room_areas).find(([_, [rx, ry, rw, rh]]) => x >= rx && x < rx+rw && y >= ry && y < ry+rh);
      if (room) div.classList.add('room');
      else div.classList.add('walk');
      if (playerPositions[`${x},${y}`]) div.classList.add('player');
      div.title = `${x},${y}`;
      div.onclick = () => {
        document.getElementById('x').value = x;
        document.getElementById('y').value = y;
      };
      boardEl.appendChild(div);
    }
  }
}

function connect() {
  ws = new WebSocket(`ws://${location.host}/ws/${playerId}?token=${encodeURIComponent(token)}`);
  ws.onmessage = (ev) => {
    const data = JSON.parse(ev.data);
    if (data.type === 'state') {
      currentState = data.state;
      stateEl.textContent = JSON.stringify(data.state, null, 2);
      renderBoard(data.state);
    }
    if (data.type === 'init') {
      currentState = data.state;
      stateEl.textContent = JSON.stringify(data.state, null, 2);
      renderBoard(data.state);
    }
    if (data.type === 'chat') {
      const line = document.createElement('div');
      line.textContent = `${data.from}: ${data.text}`;
      chatEl.appendChild(line);
      chatEl.scrollTop = chatEl.scrollHeight;
    }
    if (data.type === 'suggestion_result') alert(data.card ? `Carte montrée: ${data.card}` : 'Personne ne peut réfuter.');
    if (data.type === 'accusation_result') alert(data.correct ? 'Accusation correcte !' : `Faux. Solution: ${JSON.stringify(data.solution)}`);
    if (data.type === 'game_over') alert(`Partie terminée. Vainqueur: ${data.winner}`);
  };
}

document.getElementById('connect').onclick = () => {
  if (!token) return alert('Crée un compte ou connecte-toi d’abord.');
  if (!ws || ws.readyState !== 1) connect();
  setTimeout(() => {
    ws.send(JSON.stringify({type:'set_name', name:nameEl.value || 'Joueur'}));
    ws.send(JSON.stringify({type:'set_character', character:characterEl.value}));
  }, 300);
};

document.getElementById('start').onclick = () => ws.send(JSON.stringify({type:'start_game'}));
document.getElementById('roll').onclick = () => ws.send(JSON.stringify({type:'roll', dice: Math.floor(Math.random() * 6) + 1}));
document.getElementById('send').onclick = () => ws.send(JSON.stringify({type:'chat', text:msgEl.value}));
document.getElementById('move').onclick = () => ws.send(JSON.stringify({type:'move', x:parseInt(document.getElementById('x').value, 10), y:parseInt(document.getElementById('y').value, 10)}));
document.getElementById('secret').onclick = () => ws.send(JSON.stringify({type:'secret_passage'}));
document.getElementById('suggest').onclick = () => ws.send(JSON.stringify({type:'suggestion', room:roomEl.value, suspect:suspectEl.value, weapon:weaponEl.value}));
document.getElementById('accuse').onclick = () => ws.send(JSON.stringify({type:'accusation', room:roomEl.value, suspect:suspectEl.value, weapon:weaponEl.value}));
document.getElementById('endturn').onclick = () => ws.send(JSON.stringify({type:'end_turn'}));

(async () => {
  if (token) {
    document.getElementById('authstatus').textContent = 'Token local trouvé';
  }
})();