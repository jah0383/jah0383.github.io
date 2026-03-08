/**
 * MNIST Debate — game.js
 * Handles ONNX inference, drawing canvas, and debate game state.
 */

// ── State ─────────────────────────────────────────────────────────────────────

const State = {
  models: {
    classifier:       null,
    sparseClassifier: null,
    truthfulAgent:    null,
    lyingAgent:       null,
  },
  modelsLoaded: false,
  activeTab: 'classify',

  // Drawing canvas
  drawing: false,
  lastX: 0, lastY: 0,

  // Current 28x28 image (Float32Array, values 0-1)
  currentImage: null,

  // Debate game
  game: {
    phase:        'idle',  // idle | setup | debate | judging | result
    kPixels:      6,
    humanRole:    'spectator', // spectator | truthful | liar | judge
    trueLabel:    -1,
    falseLabel:   -1,
    revealedMask: new Float32Array(784),  // 0/1
    reveals:      [],        // [{turn, agent, pixelIdx}]
    currentTurn:  0,
    winner:       null,
    judgeVerdict: -1,
    waitingForHuman: false,
  }
};

// ── Model Loading ──────────────────────────────────────────────────────────────

async function loadModels() {
  const statusEl = document.getElementById('model-status');
  const names = [
    ['classifier',       'models/classifier.onnx'],
    ['sparseClassifier', 'models/sparse_classifier.onnx'],
    ['truthfulAgent',    'models/truthful_agent.onnx'],
    ['lyingAgent',       'models/lying_agent.onnx'],
  ];

  statusEl.textContent = 'Loading models…';
  statusEl.className = 'status loading';
//   let x = await ort.InferenceSession.create('models/classifier.onnx');
  try {
    for (const [key, path] of names) {
    //   console.log(path)
    //   State.models[key] = await ort.InferenceSession.create(path);
        State.models[key] = await ort.InferenceSession.create(path, {
            executionProviders: ['wasm']
        });
        statusEl.textContent = `Loading… ${key}`;
    }
    State.modelsLoaded = true;
    statusEl.textContent = '✓ Models loaded';
    statusEl.className = 'status ok';
    document.getElementById('classify-btn').disabled = false;
    document.getElementById('start-debate-btn').disabled = false;
  } catch (e) {
    statusEl.textContent = `⚠ Model load failed: ${e.message} — make sure .onnx files are in /models/`;
    statusEl.className = 'status error';
    console.error(e);
  }
}

// ── Tensor Utilities ───────────────────────────────────────────────────────────

function softmax(logits) {
  const max = Math.max(...logits);
  const exps = logits.map(x => Math.exp(x - max));
  const sum = exps.reduce((a, b) => a + b, 0);
  return exps.map(x => x / sum);
}

function maskedArgmax(logits, mask) {
  // Returns index of max logit among unmasked pixels
  let bestIdx = -1, bestVal = -Infinity;
  for (let i = 0; i < logits.length; i++) {
    if (mask[i] === 0 && logits[i] > bestVal) {
      bestVal = logits[i];
      bestIdx = i;
    }
  }
  return bestIdx;
}

function oneHot(label, n = 10) {
  const arr = new Float32Array(n);
  arr[label] = 1.0;
  return arr;
}

// ── Classifier Inference ───────────────────────────────────────────────────────

async function runClassifier(imageData28x28, useSparse = false) {
  const model = useSparse ? State.models.sparseClassifier : State.models.classifier;
  const tensor = new ort.Tensor('float32', imageData28x28, [1, 1, 28, 28]);
  const results = await model.run({ image: tensor });
  const logits = Array.from(results.logits.data);
  return softmax(logits);
}

// ── Agent Inference ────────────────────────────────────────────────────────────

async function runAgent(agentKey, imageFlat, revealedMask, myClaim, oppClaim) {
  const model = State.models[agentKey];
  const feeds = {
    image_flat:    new ort.Tensor('float32', imageFlat,    [1, 784]),
    revealed_mask: new ort.Tensor('float32', revealedMask, [1, 784]),
    my_claim:      new ort.Tensor('float32', oneHot(myClaim),  [1, 10]),
    opp_claim:     new ort.Tensor('float32', oneHot(oppClaim), [1, 10]),
  };
  const results = await model.run(feeds);
  return Array.from(results.pixel_logits.data);  // (784,) logits
}

// ── Drawing Canvas ─────────────────────────────────────────────────────────────

function initDrawCanvas() {
  const canvas = document.getElementById('draw-canvas');
  const ctx = canvas.getContext('2d');

  ctx.fillStyle = '#000';
  ctx.fillRect(0, 0, 280, 280);
  ctx.strokeStyle = '#fff';
  ctx.lineWidth = 18;
  ctx.lineCap = 'round';
  ctx.lineJoin = 'round';

  function getPos(e) {
    const rect = canvas.getBoundingClientRect();
    const touch = e.touches ? e.touches[0] : e;
    return {
      x: (touch.clientX - rect.left) * (280 / rect.width),
      y: (touch.clientY - rect.top)  * (280 / rect.height),
    };
  }

  canvas.addEventListener('mousedown', e => {
    State.drawing = true;
    const { x, y } = getPos(e);
    State.lastX = x; State.lastY = y;
  });

  canvas.addEventListener('mousemove', e => {
    if (!State.drawing) return;
    const { x, y } = getPos(e);
    ctx.beginPath();
    ctx.moveTo(State.lastX, State.lastY);
    ctx.lineTo(x, y);
    ctx.stroke();
    State.lastX = x; State.lastY = y;
  });

  canvas.addEventListener('mouseup',    () => { State.drawing = false; });
  canvas.addEventListener('mouseleave', () => { State.drawing = false; });

  // Touch support
  canvas.addEventListener('touchstart', e => { e.preventDefault(); State.drawing = true; const p = getPos(e); State.lastX = p.x; State.lastY = p.y; });
  canvas.addEventListener('touchmove',  e => { e.preventDefault(); if (!State.drawing) return; const { x, y } = getPos(e); ctx.beginPath(); ctx.moveTo(State.lastX, State.lastY); ctx.lineTo(x, y); ctx.stroke(); State.lastX = x; State.lastY = y; });
  canvas.addEventListener('touchend',   e => { e.preventDefault(); State.drawing = false; });
}

function clearDrawCanvas() {
  const canvas = document.getElementById('draw-canvas');
  const ctx = canvas.getContext('2d');
  ctx.fillStyle = '#000';
  ctx.fillRect(0, 0, 280, 280);
  State.currentImage = null;
  document.getElementById('classify-result').innerHTML = '';
}

function getCanvasAs28x28() {
  const canvas = document.getElementById('draw-canvas');
  const offscreen = document.createElement('canvas');
  offscreen.width = 28; offscreen.height = 28;
  const ctx = offscreen.getContext('2d');
  ctx.drawImage(canvas, 0, 0, 28, 28);
  const imgData = ctx.getImageData(0, 0, 28, 28);
  const flat = new Float32Array(784);
  for (let i = 0; i < 784; i++) {
    flat[i] = imgData.data[i * 4] / 255;  // R channel (grayscale)
  }
  console.log(flat)
  return flat;
}


// ── Classification Demo ────────────────────────────────────────────────────────

async function classify() {
  if (!State.modelsLoaded) return;
  const useSparse = document.getElementById('model-select').value === 'sparse';
  const imageFlat = getCanvasAs28x28();

  // Reshape to (1,1,28,28) for CNN
  const image28 = new Float32Array(784);
  image28.set(imageFlat);

  const probs = await runClassifier(image28, useSparse);
  const pred = probs.indexOf(Math.max(...probs));

  State.currentImage = imageFlat;
  
  renderClassifyResult(probs, pred);
}

function renderClassifyResult(probs, pred) {
  const el = document.getElementById('classify-result');
  const modelLabel = document.getElementById('model-select').value === 'sparse'
    ? 'Sparse Classifier' : 'Standard Classifier';

  el.innerHTML = `
    <div class="result-header">
      <span class="result-pred">${pred}</span>
      <span class="result-meta">${modelLabel} · ${(probs[pred] * 100).toFixed(1)}% confidence</span>
    </div>
    <div class="prob-bars">
      ${probs.map((p, i) => `
        <div class="prob-row ${i === pred ? 'top' : ''}">
          <span class="prob-label">${i}</span>
          <div class="prob-bar-wrap">
            <div class="prob-bar" style="width:${(p * 100).toFixed(1)}%"></div>
          </div>
          <span class="prob-val">${(p * 100).toFixed(1)}%</span>
        </div>
      `).join('')}
    </div>
  `;
}

// ── Pixel Grid Rendering ───────────────────────────────────────────────────────

function renderPixelGrid(canvasId, imageFlat, revealedMask, reveals) {
  const canvas = document.getElementById(canvasId);
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  const CELL = canvas.width / 28;

  ctx.clearRect(0, 0, canvas.width, canvas.height);

  for (let py = 0; py < 28; py++) {
    for (let px = 0; px < 28; px++) {
      const idx = py * 28 + px;
      const x = px * CELL, y = py * CELL;
      if (revealedMask && revealedMask[idx] === 1) {
        // Revealed: show actual pixel value
        const val = imageFlat ? Math.round(imageFlat[idx] * 255) : 0;
        ctx.fillStyle = `rgb(${val},${val},${val})`;
      } else {
        // Unrevealed: dark cell with subtle grid
        ctx.fillStyle = '#0e0e1c';
      }
      ctx.fillRect(x, y, CELL, CELL);

      // Grid lines
      ctx.strokeStyle = '#1e1e2e';
      ctx.lineWidth = 0.5;
      ctx.strokeRect(x, y, CELL, CELL);
    }
  }

  // Highlight reveals with colored borders
  if (reveals) {
    for (const { agent, pixelIdx, turn } of reveals) {
      const py = Math.floor(pixelIdx / 28);
      const px = pixelIdx % 28;
      const x = px * CELL, y = py * CELL;
      ctx.strokeStyle = agent === 'truthful' ? '#3dffa0' : '#ff4d6b';
      ctx.lineWidth = 2;
      ctx.strokeRect(x + 1, y + 1, CELL - 2, CELL - 2);

      // Turn number label
      ctx.fillStyle = agent === 'truthful' ? '#3dffa0' : '#ff4d6b';
      ctx.font = `bold ${Math.max(6, CELL * 0.5)}px "Courier Prime", monospace`;
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText(turn + 1, x + CELL / 2, y + CELL / 2);
    }
  }
}

// ── Debate Game ────────────────────────────────────────────────────────────────

function initDebate() {
  if (!State.modelsLoaded) {
    alert('Models not loaded yet. Please wait.');
    return;
  }

  const g = State.game;
  g.kPixels   = parseInt(document.getElementById('k-pixels').value);
  g.humanRole = document.getElementById('human-role').value;

  // Use drawn image if available, otherwise pick a random MNIST-like noise
  // (in production, users will draw their digit)
  const imageFlat = getCanvasAs28x28();
//   const hasContent = imageFlat.some(v => v > 0.1);
  const flat = new Float32Array(784);
  for (let i = 0; i < 784; i++) {
    flat[i] = 1  // R channel (grayscale)
  }
  renderPixelGrid('judge-canvas', imageFlat, flat, null);
//   if (!hasContent) {
//     alert('Please draw a digit on the canvas first (or switch to the Classify tab to draw one).');
//     return;
//   }

  State.currentImage = imageFlat;

  // Assign claims
  // Truthful agent always claims the classifier's top prediction
  // Liar gets a random different class
  runClassifier(new Float32Array(imageFlat), false).then(probs => {
    g.trueLabel  = probs.indexOf(Math.max(...probs));
    const others = [...Array(10).keys()].filter(i => i !== g.trueLabel);
    g.falseLabel = others[Math.floor(Math.random() * others.length)];

    g.revealedMask   = new Float32Array(784);
    g.reveals        = [];
    g.currentTurn    = 0;
    g.winner         = null;
    g.judgeVerdict   = -1;
    g.waitingForHuman = false;
    g.phase          = 'debate';

    renderDebateUI();
    updateDebateInfo();

    // If AI goes first, kick it off
    if (g.humanRole !== 'spectator') {
      scheduleNextTurn();
    } else {
      runFullDebateAI();
    }
  });
}

async function runFullDebateAI() {
  // Spectator mode: run all turns automatically
  const g = State.game;
  for (let t = 0; t < g.kPixels; t++) {
    await delay(600);
    await doAITurn(t % 2 === 0 ? 'truthful' : 'liar');
    renderDebateBoards();
    updateDebateInfo();
  }
  await delay(400);
  await finishDebate();
}

async function scheduleNextTurn() {
  const g = State.game;
  if (g.currentTurn >= g.kPixels) {
    await finishDebate();
    return;
  }

  const agentThisTurn = g.currentTurn % 2 === 0 ? 'truthful' : 'liar';

  const humanIsThisAgent =
    (agentThisTurn === 'truthful' && g.humanRole === 'truthful') ||
    (agentThisTurn === 'liar'     && g.humanRole === 'liar');

  if (humanIsThisAgent) {
    // Wait for human click on pixel grid
    g.waitingForHuman = true;
    updateDebateInfo();
    setGridClickable(true);
  } else {
    // AI takes this turn
    await delay(700);
    await doAITurn(agentThisTurn);
    renderDebateBoards();
    updateDebateInfo();
    scheduleNextTurn();
  }
}

async function doAITurn(agentName) {
  const g = State.game;
  const agentKey  = agentName === 'truthful' ? 'truthfulAgent' : 'lyingAgent';
  const myClaim   = agentName === 'truthful' ? g.trueLabel  : g.falseLabel;
  const oppClaim  = agentName === 'truthful' ? g.falseLabel : g.trueLabel;

  const logits = await runAgent(agentKey, State.currentImage, g.revealedMask, myClaim, oppClaim);
  const pixelIdx = maskedArgmax(logits, g.revealedMask);

  revealPixel(agentName, pixelIdx);
}

function revealPixel(agentName, pixelIdx) {
  const g = State.game;
  g.revealedMask[pixelIdx] = 1;
  g.reveals.push({ agent: agentName, pixelIdx, turn: g.currentTurn });
  g.currentTurn++;
}

async function handleHumanPixelClick(pixelIdx) {
  const g = State.game;
  if (!g.waitingForHuman) return;
  if (g.revealedMask[pixelIdx] === 1) return;  // already revealed

  g.waitingForHuman = false;
  setGridClickable(false);

  const agentThisTurn = (g.currentTurn % 2 === 0) ? 'truthful' : 'liar';
  revealPixel(agentThisTurn, pixelIdx);
  renderDebateBoards();
  updateDebateInfo();
  scheduleNextTurn();
}

async function finishDebate() {
  const g = State.game;
  g.phase = 'judging';
  updateDebateInfo();

  // Build masked image for judge
  const maskedImg = new Float32Array(784);
  for (let i = 0; i < 784; i++) {
    maskedImg[i] = State.currentImage[i] * g.revealedMask[i];
  }

  if (g.humanRole === 'judge') {
    // Human judges — show them only the revealed pixels and ask for vote
    renderJudgeVoteUI();
    return;
  }

  // AI judge (sparse classifier)
  const probs = await runClassifier(maskedImg, true);
  g.judgeVerdict = probs.indexOf(Math.max(...probs));
  g.winner = (g.judgeVerdict === g.trueLabel) ? 'truthful' : 'liar';
  g.phase = 'result';
  renderResult();
}

async function submitHumanJudgeVote(vote) {
  const g = State.game;
  g.judgeVerdict = vote;
  g.winner = (vote === g.trueLabel) ? 'truthful' : 'liar';
  g.phase = 'result';
  renderResult();
}

// ── Debate UI Rendering ────────────────────────────────────────────────────────

function renderDebateUI() {
  const container = document.getElementById('debate-game');
  container.style.display = 'block';
  document.getElementById('debate-setup').style.display = 'none';
  renderDebateBoards();
}

function renderDebateBoards() {
  const g = State.game;

  // Agent view: full image (only shown to agents, not judge)
  if (g.humanRole !== 'judge' && g.humanRole !== 'spectator') {
    renderPixelGrid('agent-canvas', State.currentImage, State.currentImage, null);
  } else {
    // Spectator/judge: show full image for context in spectator mode
    if (g.humanRole === 'spectator') {
      renderPixelGrid('agent-canvas', State.currentImage, State.currentImage, null);
    }
  }

  // Judge view: only revealed pixels
  const judgeReveals = g.reveals.map(r => r);
  renderPixelGrid('judge-canvas', State.currentImage, g.revealedMask, judgeReveals);
}

function updateDebateInfo() {
  const g = State.game;
  const el = document.getElementById('debate-info');
  if (!el) return;

  const agentThisTurn = g.currentTurn % 2 === 0 ? 'truthful' : 'liar';
  const turnLabel = g.waitingForHuman ? '← Click a pixel to reveal' : '';

  const roleColor = { truthful: '#3dffa0', liar: '#ff4d6b', judge: '#7b8cde', spectator: '#aaa' };
  const agentColor = agentThisTurn === 'truthful' ? '#3dffa0' : '#ff4d6b';

  el.innerHTML = `
    <div class="info-grid">
      <div class="info-block">
        <div class="info-label">YOUR ROLE</div>
        <div class="info-val" style="color:${roleColor[g.humanRole]}">${g.humanRole.toUpperCase()}</div>
      </div>
      <div class="info-block">
        <div class="info-label">TRUTHFUL CLAIMS</div>
        <div class="info-val" style="color:#3dffa0">${g.trueLabel}</div>
      </div>
      <div class="info-block">
        <div class="info-label">LIAR CLAIMS</div>
        <div class="info-val" style="color:#ff4d6b">${g.falseLabel}</div>
      </div>
      <div class="info-block">
        <div class="info-label">TURN</div>
        <div class="info-val">${Math.min(g.currentTurn + 1, g.kPixels)} / ${g.kPixels}</div>
      </div>
    </div>
    ${g.phase === 'debate' ? `
      <div class="turn-banner" style="border-color:${agentColor};color:${agentColor}">
        ${agentThisTurn.toUpperCase()} AGENT's TURN ${turnLabel}
      </div>
    ` : ''}
    ${g.phase === 'judging' && g.humanRole !== 'judge' ? `
      <div class="turn-banner" style="border-color:#7b8cde;color:#7b8cde">JUDGING…</div>
    ` : ''}
  `;
}

function renderJudgeVoteUI() {
  const el = document.getElementById('judge-vote-area');
  if (!el) return;
  el.style.display = 'block';
  el.innerHTML = `
    <div class="judge-prompt">
      You are the judge. Based only on the revealed pixels, which digit do you think this is?
    </div>
    <div class="vote-buttons">
      ${[...Array(10).keys()].map(i => `
        <button class="vote-btn" onclick="submitHumanJudgeVote(${i})">${i}</button>
      `).join('')}
    </div>
  `;
}

function renderResult() {
  const g = State.game;
  const resultEl = document.getElementById('debate-result');
  resultEl.style.display = 'block';

  const judgeVoteEl = document.getElementById('judge-vote-area');
  if (judgeVoteEl) judgeVoteEl.style.display = 'none';

  const winnerColor = g.winner === 'truthful' ? '#3dffa0' : '#ff4d6b';
  const winnerLabel = g.winner === 'truthful' ? 'TRUTHFUL WINS' : 'LIAR WINS';

  resultEl.innerHTML = `
    <div class="result-banner" style="border-color:${winnerColor};color:${winnerColor}">
      ${winnerLabel}
    </div>
    <div class="result-details">
      <span>True digit: <strong style="color:#3dffa0">${g.trueLabel}</strong></span>
      <span>Liar claimed: <strong style="color:#ff4d6b">${g.falseLabel}</strong></span>
      <span>Judge predicted: <strong style="color:#7b8cde">${g.judgeVerdict}</strong></span>
    </div>
    <button class="btn-secondary" onclick="resetDebate()">Play Again</button>
  `;

  // Show full image in agent panel
  renderPixelGrid('agent-canvas', State.currentImage, State.currentImage, null);
}

function resetDebate() {
  document.getElementById('debate-game').style.display = 'none';
  document.getElementById('debate-setup').style.display = 'block';
  document.getElementById('debate-result').style.display = 'none';
  const judgeVoteEl = document.getElementById('judge-vote-area');
  if (judgeVoteEl) judgeVoteEl.style.display = 'none';
  setGridClickable(false);
}

// ── Grid Click Handler ─────────────────────────────────────────────────────────

function setGridClickable(enabled) {
  const canvas = document.getElementById('judge-canvas');
  if (!canvas) return;
  canvas.style.cursor = enabled ? 'crosshair' : 'default';
  canvas.onclick = enabled ? (e) => {
    const rect = canvas.getBoundingClientRect();
    const x = (e.clientX - rect.left) * (canvas.width / rect.width);
    const y = (e.clientY - rect.top)  * (canvas.height / rect.height);
    const CELL = canvas.width / 28;
    const px = Math.floor(x / CELL);
    const py = Math.floor(y / CELL);
    const idx = py * 28 + px;
    handleHumanPixelClick(idx);
  } : null;
}

// ── Tab Switching ──────────────────────────────────────────────────────────────

function switchTab(tab) {
  State.activeTab = tab;
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
  document.querySelector(`.tab-btn[data-tab="${tab}"]`).classList.add('active');
  document.getElementById(`tab-${tab}`).classList.add('active');
}

// ── Utility ────────────────────────────────────────────────────────────────────

function delay(ms) { return new Promise(r => setTimeout(r, ms)); }

// ── Init ───────────────────────────────────────────────────────────────────────

window.addEventListener('DOMContentLoaded', () => {
  initDrawCanvas();
  ort.env.wasm.wasmPaths = '/js/ort/';
  ort.env.wasm.numThreads = 1;
  ort.env.wasm.simd = true;
  loadModels();

  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => switchTab(btn.dataset.tab));
  });

  document.getElementById('clear-btn').addEventListener('click', clearDrawCanvas);
  document.getElementById('classify-btn').addEventListener('click', classify);
  document.getElementById('start-debate-btn').addEventListener('click', initDebate);
});