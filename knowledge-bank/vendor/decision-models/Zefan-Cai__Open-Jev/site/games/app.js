(() => {
  'use strict';

  const $ = (id) => document.getElementById(id);
  const namespace = 'http://www.w3.org/2000/svg';
  const palette = { grid: '#24464a', line: '#507067', mint: '#94d4b5', body: '#559781', lime: '#d4f078', coral: '#fa8c72', gold: '#f0cc74', muted: '#b3cbbd' };
  const gameInfo = {
    snake: { hash: 'snake', title: 'Snake', subtitle: 'Find your next direction', kicker: '01 / Read the grid', icon: '<path d="M5 7h15v7H11v7h15v6H5V14h9" fill="none" stroke="currentColor" stroke-width="4" stroke-linejoin="round"/><circle cx="26" cy="7" r="3" fill="currentColor"/>' },
    tic_tac_toe: { hash: 'tic-tac-toe', title: 'Tic-tac-toe', subtitle: 'Make the board your own', kicker: '02 / Think one move ahead', icon: '<path d="M11 3v26M21 3v26M3 11h26M3 21h26" stroke="currentColor" stroke-width="2"/><path d="m4 4 4 4m0-4L4 8" stroke="currentColor" stroke-width="2"/><circle cx="16" cy="16" r="3" fill="none" stroke="currentColor" stroke-width="2"/>' },
    trex_runner: { hash: 'runner', title: 'Box runner', subtitle: 'Meet the next obstacle', kicker: '03 / Read the clearance', icon: '<path d="M5 12h8v13H5zM22 18h6v7h-6z" fill="currentColor"/><path d="M2 29h28M15 7l4-4 4 4m-4-4v11" stroke="currentColor" stroke-width="2" fill="none"/>' },
    tile_platformer: { hash: 'platformer', title: 'Tile platformer', subtitle: 'Mind the gap', kicker: '04 / Plan the landing', icon: '<path d="M2 25h9v5H2zM17 20h13v10H17zM7 12h6v7H7z" fill="currentColor"/><path d="M24 4v13m0-13 6 3-6 3" stroke="currentColor" stroke-width="2" fill="none"/>' }
  };
  const actions = {
    up: ['Up', 'One cell up', '↑'], right: ['Right', 'One cell right', '→'], down: ['Down', 'One cell down', '↓'], left: ['Left', 'One cell left', '←'],
    jump_short: ['Short jump', 'A short jump maneuver', '⌁'], jump_full: ['Full jump', 'A full jump maneuver', '↗'],
    duck: ['Duck', 'Lower your profile', '↓'], keep_running: ['Keep running', 'Maintain standing height', '→'],
    noop: ['Stay', 'No horizontal move', '·'], right_jump: ['Walk + jump', 'Right by 1 tile', '↗'],
    right_run: ['Run right', 'Right by 2 tiles', '⇉'], right_run_jump: ['Run + jump', 'Right by 2 tiles', '↗'], jump: ['Jump', 'No horizontal move', '↑']
  };
  const positions = ['Top left', 'Top middle', 'Top right', 'Middle left', 'Center', 'Middle right', 'Bottom left', 'Bottom middle', 'Bottom right'];
  let evidence;
  let activeGame = 'snake';
  let caseIndex = 0;
  let userChoice = null;
  let revealed = false;

  function node(tag, className, text) {
    const result = document.createElement(tag);
    if (className) result.className = className;
    if (text !== undefined) result.textContent = text;
    return result;
  }

  function svgNode(tag, attributes, text) {
    const result = document.createElementNS(namespace, tag);
    Object.entries(attributes || {}).forEach(([key, value]) => result.setAttribute(key, value));
    if (text !== undefined) result.textContent = text;
    return result;
  }

  function svgCanvas(width, height, description) {
    const svg = svgNode('svg', { viewBox: `0 0 ${width} ${height}`, role: 'img', 'aria-label': description });
    svg.append(svgNode('title', {}, description));
    return svg;
  }

  function rect(svg, x, y, width, height, fill, extra = {}) { svg.append(svgNode('rect', { x, y, width, height, fill, ...extra })); }
  function line(svg, x1, y1, x2, y2, color, extra = {}) { svg.append(svgNode('line', { x1, y1, x2, y2, stroke: color, ...extra })); }
  function label(svg, x, y, text, extra = {}) { svg.append(svgNode('text', { x, y, fill: palette.muted, 'font-size': 10, ...extra }, text)); }
  function game() { return evidence.games.find((item) => item.id === activeGame); }
  function current() { return game().cases[caseIndex]; }
  function displayAction(action) { return activeGame === 'tic_tac_toe' ? `Square ${action}` : (actions[action]?.[0] || action); }

  function validate(data) {
    if (data.schema_version !== 1 || !Array.isArray(data.games)) throw new Error('Unsupported evidence schema');
    for (const id of Object.keys(gameInfo)) {
      const selected = data.games.find((item) => item.id === id);
      if (!selected?.cases?.length) throw new Error('Game evidence missing');
      for (const item of selected.cases) {
        const options = item.record?.options;
        const probabilities = item.prediction?.probabilities;
        if (!item.record?.state || !Array.isArray(options) || !options.length || !options.every((option) => typeof option === 'string')) throw new Error('Invalid game input');
        if (!Array.isArray(probabilities) || options.length !== probabilities.length || !probabilities.every((p) => Number.isFinite(p) && p >= 0 && p <= 1)) throw new Error('Invalid model distribution');
        if (Math.abs(probabilities.reduce((sum, p) => sum + p, 0) - 1) > 1e-6) throw new Error('Incomplete model distribution');
        if (options[item.selected_index] !== item.selected_action || probabilities[item.selected_index] !== Math.max(...probabilities)) throw new Error('Model selection mismatch');
      }
    }
  }

  function createPicker() {
    Object.entries(gameInfo).forEach(([id, info]) => {
      const button = node('button', 'game-tab');
      button.type = 'button';
      button.dataset.game = id;
      button.setAttribute('aria-pressed', 'false');
      const icon = node('span', 'game-tab-icon');
      icon.setAttribute('aria-hidden', 'true');
      icon.innerHTML = `<svg viewBox="0 0 32 32">${info.icon}</svg>`;
      const copy = node('span');
      copy.append(node('strong', '', info.title), node('small', '', info.subtitle));
      button.append(icon, copy, node('span', 'game-tab-arrow', '↗'));
      button.addEventListener('click', () => {
        if (location.hash === `#${info.hash}`) setGame(id);
        else location.hash = info.hash;
      });
      $('game-picker').append(button);
    });
  }

  function setGame(id) {
    activeGame = id;
    caseIndex = 0;
    userChoice = null;
    revealed = false;
    document.querySelectorAll('.game-tab').forEach((button) => button.setAttribute('aria-pressed', String(button.dataset.game === id)));
    render();
  }

  function route() {
    const hash = location.hash.slice(1);
    const selected = Object.entries(gameInfo).find(([, info]) => info.hash === hash);
    setGame(selected?.[0] || 'snake');
  }

  function choose(index, origin) {
    if (revealed) return;
    userChoice = index;
    renderChoices();
    renderScene();
    $('reveal').disabled = false;
    $('reveal').replaceChildren(document.createTextNode('Reveal the model’s move'), node('span', '', '↗'));
    const nextFocus = origin === 'board' ? document.querySelector(`.ttt-cell[data-option="${index}"]`) : document.querySelector(`.choice[data-option="${index}"]`);
    nextFocus?.focus({ preventScroll: true });
  }

  function render() {
    const item = current();
    $('game-title').textContent = gameInfo[activeGame].title;
    $('game-kicker').textContent = gameInfo[activeGame].kicker;
    $('case-counter').replaceChildren(node('b', '', String(caseIndex + 1).padStart(2, '0')), document.createTextNode(` / ${String(game().cases.length).padStart(2, '0')}`));
    $('scene-title').textContent = item.title;
    $('decision-title').textContent = revealed ? 'The recorded decision.' : 'What would you do?';
    $('decision-instruction').textContent = revealed ? 'Every option. Original order. Saved probabilities.' : (activeGame === 'tic_tac_toe' ? 'Pick an empty square or an option below.' : 'Select a move, then reveal the model’s choice.');
    $('question').textContent = item.record.question;
    $('case-note').textContent = item.note;
    $('case-note').hidden = !revealed;
    $('source-record').textContent = JSON.stringify({ record: item.record, prediction: item.prediction, selected_index: item.selected_index, selected_action: item.selected_action, target_actions: item.target_actions, source_provenance: item.source_provenance }, null, 2);
    $('reveal').hidden = revealed;
    $('reveal').disabled = userChoice === null;
    $('reveal').replaceChildren(document.createTextNode(userChoice === null ? 'Choose your move first' : 'Reveal the model’s move'), node('span', '', '↗'));
    $('comparison').hidden = !revealed;
    $('probability-note').textContent = revealed ? 'Probabilities are over the available actions, not win probabilities. Exact values and logits are in the evidence below.' : 'Your choice stays in this browser. This page reads saved outputs; it does not call a model.';
    $('case-dots').replaceChildren();
    game().cases.forEach((entry, index) => {
      const button = node('button', 'case-dot');
      button.type = 'button';
      button.setAttribute('aria-label', `Situation ${index + 1}: ${entry.title}`);
      button.setAttribute('aria-pressed', String(index === caseIndex));
      button.append(node('span'));
      button.addEventListener('click', () => {
        caseIndex = index;
        userChoice = null;
        revealed = false;
        render();
        $('case-dots').children[index].focus({ preventScroll: true });
      });
      $('case-dots').append(button);
    });
    renderChoices();
    renderScene();
    if (revealed) renderComparison();
  }

  function renderChoices() {
    const item = current();
    $('choices').replaceChildren();
    item.record.options.forEach((action, index) => {
      const button = node('button', 'choice');
      button.type = 'button';
      button.dataset.option = index;
      button.setAttribute('aria-pressed', String(userChoice === index));
      button.disabled = revealed;
      if (userChoice === index) button.classList.add('chosen');
      if (revealed) button.classList.add('is-revealed');
      if (revealed && item.selected_index === index) button.classList.add('model-choice');
      const actionInfo = actions[action] || [];
      const copy = node('span', 'choice-copy');
      const description = activeGame === 'tic_tac_toe' ? positions[Number(action)] : activeGame === 'tile_platformer' && ['right', 'left'].includes(action) ? 'Move by 1 tile' : actionInfo[1];
      copy.append(node('span', 'choice-name', displayAction(action)), node('span', 'choice-description', description || 'Available action'));
      const key = node('span', 'choice-key', activeGame === 'tic_tac_toe' ? action : String(index + 1));
      key.setAttribute('aria-hidden', 'true');
      button.append(key);
      if (activeGame !== 'tic_tac_toe') {
        const icon = node('span', 'choice-icon', actionInfo[2] || '·');
        icon.setAttribute('aria-hidden', 'true');
        button.append(icon);
      }
      button.append(copy);
      const right = node('span', 'choice-right');
      if (revealed) {
        const probability = item.prediction.probabilities[index];
        right.append(node('span', '', probability > 0 && probability < .0001 ? '<0.01%' : `${(probability * 100).toFixed(2)}%`));
        right.title = `Exact probability: ${probability}`;
        const tags = [];
        if (index === item.selected_index) tags.push('Model');
        if (index === userChoice) tags.push('You');
        if (tags.length) right.append(node('span', 'choice-tag', tags.join(' + ')));
        const track = node('span', 'probability-track');
        track.setAttribute('aria-hidden', 'true');
        const bar = node('span', 'probability-bar');
        bar.style.width = `${probability * 100}%`;
        track.append(bar);
        button.append(track);
        button.setAttribute('aria-label', `${displayAction(action)}, probability ${(probability * 100).toFixed(4)} percent${tags.length ? `, ${tags.join(' and ')} choice` : ''}`);
      } else right.append(node('span', 'choice-pick-dot'));
      button.append(right);
      button.addEventListener('click', () => choose(index, 'choice'));
      $('choices').append(button);
    });
  }

  function renderComparison() {
    const item = current();
    const same = userChoice === item.selected_index;
    $('comparison').replaceChildren(node('h3', '', same ? 'Same move.' : 'Two different calls.'));
    const yours = node('p');
    yours.append(document.createTextNode('You chose '), node('strong', '', displayAction(item.record.options[userChoice])), document.createTextNode('.'));
    const model = node('p');
    model.append(document.createTextNode('Open-Jev chose '), node('strong', '', displayAction(item.selected_action)), document.createTextNode(` (${(item.prediction.probabilities[item.selected_index] * 100).toFixed(2)}%).`));
    $('comparison').append(yours, model);
    const targetNames = (item.target_actions || []).map(displayAction).join(', ');
    const note = item.matches_target ? `The recorded choice matches a supplied reference action: ${targetNames}.` : `The recorded choice differs from the supplied reference: ${targetNames}.`;
    $('comparison').append(node('p', 'reference-note', note));
  }

  function facts(values) {
    $('facts').replaceChildren();
    values.forEach(([key, value]) => {
      const fact = node('div', 'fact');
      fact.append(node('span', '', key), node('strong', '', String(value)));
      $('facts').append(fact);
    });
  }

  function legends(items) {
    $('scene-legend').replaceChildren();
    items.forEach(([kind, text]) => {
      const item = node('span', 'legend-item');
      if (kind) item.append(node('span', `legend-dot ${kind}`));
      item.append(document.createTextNode(text));
      $('scene-legend').append(item);
    });
  }

  function renderScene() {
    $('scene').replaceChildren();
    const state = current().record.state;
    if (activeGame === 'snake') drawSnake(state);
    else if (activeGame === 'tic_tac_toe') drawTicTacToe(state);
    else if (activeGame === 'trex_runner') drawRunner(state);
    else drawPlatformer(state);
  }

  function drawSnake(state) {
    const size = 276 / Math.max(state.width, state.height);
    const startX = (400 - state.width * size) / 2;
    const startY = 28;
    const head = state.snake_head_first[0];
    const svg = svgCanvas(400, 325, `Saved Snake board, ${state.width} by ${state.height}. Head at (${head.join(', ')}), moving ${state.direction}. Food at (${state.food.join(', ')}). Body head-first: ${state.snake_head_first.map((p) => p.join(',')).join('; ')}. Coordinates start at top left; x increases right and y increases down.`);
    for (let y = 0; y < state.height; y++) {
      label(svg, startX - 13, startY + y * size + size / 2 + 3, y, { 'text-anchor': 'middle', 'font-size': 8 });
      for (let x = 0; x < state.width; x++) rect(svg, startX + x * size + 2, startY + y * size + 2, size - 4, size - 4, palette.grid, { rx: 4 });
    }
    for (let x = 0; x < state.width; x++) label(svg, startX + x * size + size / 2, startY - 9, x, { 'text-anchor': 'middle', 'font-size': 8 });
    state.snake_head_first.slice().reverse().forEach(([x, y], reversedIndex) => {
      const isHead = reversedIndex === state.snake_head_first.length - 1;
      rect(svg, startX + x * size + 4, startY + y * size + 4, size - 8, size - 8, isHead ? palette.lime : palette.body, { rx: 5 });
    });
    const cx = startX + head[0] * size + size / 2;
    const cy = startY + head[1] * size + size / 2;
    const direction = { up: 0, right: 90, down: 180, left: 270 }[state.direction];
    svg.append(svgNode('path', { d: 'M-5 3 0-3 5 3', transform: `translate(${cx},${cy}) rotate(${direction})`, fill: 'none', stroke: '#284835', 'stroke-width': 2.4, 'stroke-linecap': 'round', 'stroke-linejoin': 'round' }));
    if (state.food) {
      const fx = startX + (state.food[0] + .5) * size;
      const fy = startY + (state.food[1] + .5) * size;
      svg.append(svgNode('circle', { cx: fx, cy: fy + 1, r: size * .18, fill: palette.coral }));
      line(svg, fx, fy - size * .12, fx + 3, fy - size * .25, palette.coral, { 'stroke-width': 2 });
    }
    if (userChoice !== null) {
      const action = current().record.options[revealed ? current().selected_index : userChoice];
      const [dx, dy] = { up: [0, -1], right: [1, 0], down: [0, 1], left: [-1, 0] }[action];
      const tx = head[0] + dx;
      const ty = head[1] + dy;
      if (tx >= 0 && tx < state.width && ty >= 0 && ty < state.height) {
        rect(svg, startX + tx * size + 4, startY + ty * size + 4, size - 8, size - 8, 'none', { rx: 5, stroke: palette.gold, 'stroke-width': 2, 'stroke-dasharray': '4 3' });
        label(svg, startX + (tx + .5) * size, startY + (ty + .5) * size + 3, revealed ? 'M' : 'YOU', { fill: palette.gold, 'text-anchor': 'middle', 'font-size': revealed ? 10 : 8 });
      }
    }
    $('scene').append(svg);
    legends([['', 'Head: lime / arrow'], ['body', 'Body'], ['food', 'Food'], ...(userChoice !== null ? [['goal', revealed ? 'Model direction' : 'Your direction']] : [])]);
    facts([['Board', `${state.width} × ${state.height}`], ['Heading', state.direction], ['Food', `(${state.food.join(', ')})`]]);
    $('scene-caption').textContent = 'Coordinates: x → right, y ↓ down; (0, 0) is top left. The outline marks a proposed direction; the snake has not moved.';
  }

  function drawTicTacToe(state) {
    const board = node('div', 'ttt-board');
    board.setAttribute('role', 'group');
    board.setAttribute('aria-label', `Saved tic-tac-toe board. ${state.current_player} to play. Squares zero to eight, row-major.`);
    const cells = state.board.join('').split('');
    cells.forEach((mark, square) => {
      const option = current().record.options.indexOf(String(square));
      const cell = node('button', `ttt-cell ${mark === 'O' ? 'is-o' : ''} ${mark === '.' ? 'is-empty' : ''}`);
      cell.type = 'button';
      cell.disabled = mark !== '.' || revealed || option < 0;
      cell.dataset.option = option;
      let displayed = mark === '.' ? '+' : mark;
      let status = mark === '.' ? 'empty' : `occupied by ${mark}`;
      if (option >= 0 && userChoice === option) {
        cell.classList.add('chosen');
        displayed = state.current_player;
        status = `your proposed ${state.current_player}`;
      }
      if (revealed && option === current().selected_index) {
        cell.classList.add('model-choice');
        displayed = state.current_player;
        status = `model proposed ${state.current_player}`;
      }
      cell.setAttribute('aria-label', `Square ${square}, ${positions[square]}, ${status}`);
      cell.append(node('span', 'ttt-index', square), node('span', '', displayed));
      cell.addEventListener('click', () => choose(option, 'board'));
      board.append(cell);
    });
    $('scene').append(board);
    legends([['', `${state.current_player} to play`], ['food', 'Existing O'], ...(revealed ? [['goal', 'Model = proposed mark']] : [])]);
    facts([['Current player', state.current_player], ['Empty squares', cells.filter((mark) => mark === '.').length], ['Square numbering', '0–8, row-major']]);
    $('scene-caption').textContent = 'Click an empty square to propose a move. Outlined marks are proposals; existing pieces and the saved board stay unchanged.';
  }

  function drawRunner(state) {
    const obstacle = state.target_obstacle;
    const geometry = state.runner_geometry;
    const x0 = 47;
    const floor = 226;
    const scale = 480 / (geometry.obstacle_start_x + obstacle.width + 2);
    const obstacleX = x0 + geometry.obstacle_start_x * scale;
    const svg = svgCanvas(600, 305, `Saved original box runner state. Player width ${geometry.player_width}, standing height ${geometry.standing_height}, duck height ${geometry.duck_height}. ${obstacle.kind} obstacle at x ${geometry.obstacle_start_x}, width ${obstacle.width}, height ${obstacle.height}, bottom ${obstacle.bottom}. Current speed ${state.current_speed}.`);
    for (let x = 0; x <= 16; x++) line(svg, x0 + x * scale, 68, x0 + x * scale, floor, palette.grid, { 'stroke-dasharray': '2 6' });
    [1, 2, 3, 4].forEach((height) => {
      line(svg, x0, floor - height * scale, 560, floor - height * scale, palette.grid, { 'stroke-dasharray': '2 6' });
      label(svg, x0 - 13, floor - height * scale + 3, height, { 'text-anchor': 'middle', 'font-size': 9 });
    });
    line(svg, x0 - 10, floor, 560, floor, palette.line, { 'stroke-width': 2 });
    rect(svg, x0, floor - geometry.standing_height * scale, geometry.player_width * scale, geometry.standing_height * scale, palette.lime, { rx: 3 });
    const playerBottom = floor - geometry.duck_height * scale;
    line(svg, x0 - 6, playerBottom, x0 + geometry.player_width * scale + 6, playerBottom, '#416144', { 'stroke-width': 1.5, 'stroke-dasharray': '3 3' });
    rect(svg, obstacleX, floor - (obstacle.bottom + obstacle.height) * scale, obstacle.width * scale, obstacle.height * scale, palette.coral, { rx: 2 });
    label(svg, x0 + geometry.player_width * scale / 2, floor + 20, 'PLAYER', { 'text-anchor': 'middle', 'font-size': 9 });
    label(svg, obstacleX + obstacle.width * scale / 2, floor + 20, 'OBSTACLE', { 'text-anchor': 'middle', 'font-size': 9 });
    line(svg, x0 + geometry.player_width * scale + 10, floor + 46, obstacleX, floor + 46, palette.line);
    label(svg, (x0 + geometry.player_width * scale + 10 + obstacleX) / 2, floor + 41, `obstacle starts at x = ${geometry.obstacle_start_x}`, { 'text-anchor': 'middle', 'font-size': 9 });
    label(svg, 300, 32, obstacle.kind.replaceAll('_', ' ').toUpperCase(), { 'text-anchor': 'middle', 'font-size': 12, fill: palette.coral });
    $('scene').append(svg);
    legends([['', 'Standing player'], ['food', 'Obstacle box'], [null, 'Dotted player line = duck height']]);
    facts([['Obstacle W × H', `${obstacle.width} × ${obstacle.height}`], ['Bottom / ground', obstacle.bottom], ['Speed', state.current_speed]]);
    $('scene-caption').textContent = `Original box physics. Standing height ${geometry.standing_height}; duck height ${geometry.duck_height}. Dimensions use a shared scale. Launch timing is handled by the controller, not by this illustration.`;
  }

  function drawPlatformer(state) {
    const columns = state.terrain.columns;
    const player = state.player;
    const visible = Math.min(18, columns.length);
    const start = Math.max(0, Math.min(columns.length - visible, player.x - 4));
    const end = start + visible;
    const cell = 29;
    const x0 = 35;
    const floor = 186;
    const unit = 25;
    const svg = svgCanvas(600, 305, `Saved tile platformer state. Detail shows columns ${start} through ${end - 1}; overview shows all ${columns.length} columns. Player x ${player.x}, feet height ${player.y}, ${player.jump_phase}; jump tick ${state.trajectory.jump_tick}. Flag at column ${state.terrain.flag_x}. Terrain columns: ${columns.map((height) => height === null ? 'gap' : height).join(', ')}.`);
    label(svg, x0, 23, `DETAIL / COLUMNS ${start}–${end - 1}`, { 'font-size': 9 });
    for (let height = 0; height <= 4; height++) {
      line(svg, x0, floor - height * unit, x0 + visible * cell, floor - height * unit, palette.grid, { 'stroke-dasharray': '2 6' });
      label(svg, x0 - 12, floor - height * unit + 3, height, { 'font-size': 8, 'text-anchor': 'middle' });
    }
    columns.slice(start, end).forEach((height, index) => {
      const left = x0 + index * cell;
      if (height !== null) {
        rect(svg, left + 1, floor - height * unit, cell - 2, height * unit + 20, palette.grid, { rx: 2 });
        rect(svg, left + 1, floor - height * unit, cell - 2, 4, palette.body, { rx: 1 });
        for (let bottom = floor - height * unit + 13; bottom < floor + 20; bottom += 15) line(svg, left + 7, bottom, left + cell - 7, bottom, '#365950');
      } else label(svg, left + cell / 2, floor + 15, '×', { 'text-anchor': 'middle', fill: palette.coral, 'font-size': 11 });
      if ((index + start) % 2 === 0) label(svg, left + cell / 2, floor + 36, index + start, { 'font-size': 8, 'text-anchor': 'middle' });
    });
    const playerX = x0 + (player.x - start) * cell + cell / 2;
    const playerY = floor - player.y * unit;
    rect(svg, playerX - 9, playerY - 19, 18, 19, palette.lime, { rx: 3 });
    rect(svg, playerX + 3, playerY - 14, 3, 3, '#2d513a');
    label(svg, playerX, playerY - 29, 'YOU', { fill: palette.lime, 'font-size': 9, 'text-anchor': 'middle' });
    if (state.terrain.flag_x >= start && state.terrain.flag_x < end) {
      const flagX = x0 + (state.terrain.flag_x - start) * cell + cell / 2;
      const flagGround = floor - (columns[state.terrain.flag_x] || 0) * unit;
      line(svg, flagX, flagGround, flagX, flagGround - 44, palette.gold, { 'stroke-width': 2 });
      svg.append(svgNode('path', { d: `M${flagX} ${flagGround - 44}h20l-7 8 7 8h-20z`, fill: palette.gold }));
    }
    const miniCell = visible * cell / columns.length;
    const miniTop = 268;
    label(svg, x0, 247, `FULL TERRAIN / ${columns.length} COLUMNS`, { 'font-size': 9 });
    columns.forEach((height, index) => {
      if (height !== null) rect(svg, x0 + index * miniCell + .7, miniTop - height * 4, miniCell - 1.4, 8 + height * 4, palette.body, { rx: .5 });
      else line(svg, x0 + index * miniCell + 1, miniTop + 4, x0 + (index + 1) * miniCell - 1, miniTop + 4, palette.coral, { 'stroke-width': 2 });
    });
    rect(svg, x0 + start * miniCell - 2, miniTop - 15, visible * miniCell + 4, 30, 'none', { rx: 3, stroke: '#9cbea7', 'stroke-width': 1 });
    svg.append(svgNode('circle', { cx: x0 + (player.x + .5) * miniCell, cy: miniTop - 9, r: 3, fill: palette.lime }));
    label(svg, x0 + (state.terrain.flag_x + .5) * miniCell, miniTop - 10, '⚑', { fill: palette.gold, 'text-anchor': 'middle', 'font-size': 14 });
    label(svg, x0, 300, '0', { 'font-size': 8 });
    label(svg, x0 + columns.length * miniCell, 300, columns.length - 1, { 'font-size': 8, 'text-anchor': 'end' });
    $('scene').append(svg);
    legends([['', 'Player'], ['food', 'Gap'], ['goal', 'Flag'], ['body', 'Solid terrain']]);
    facts([['Position (x, y)', `(${player.x}, ${player.y})`], ['Motion / tick', `${player.jump_phase} / ${state.trajectory.jump_tick}`], ['Flag column', state.terrain.flag_x]]);
    $('scene-caption').textContent = 'Original tile simulator. Detail and full-terrain overview show the same saved state. y measures feet height; airborne jump requests do not restart a jump.';
  }

  $('reveal').addEventListener('click', () => {
    if (userChoice === null || revealed) return;
    revealed = true;
    render();
    $('comparison').tabIndex = -1;
    $('comparison').focus({ preventScroll: true });
  });
  $('reset').addEventListener('click', () => {
    userChoice = null;
    revealed = false;
    render();
  });
  $('next').addEventListener('click', () => {
    caseIndex = (caseIndex + 1) % game().cases.length;
    userChoice = null;
    revealed = false;
    render();
  });

  fetch('./evidence.json').then((response) => {
    if (!response.ok) throw new Error('Evidence request failed');
    return response.json();
  }).then((data) => {
    validate(data);
    evidence = data;
    createPicker();
    (data.limitations || []).forEach((text) => $('evidence-limitations').append(node('li', '', text)));
    route();
    window.addEventListener('hashchange', route);
    $('loading').hidden = true;
    $('arcade').hidden = false;
  }).catch(() => {
    $('loading').hidden = true;
    $('arcade').hidden = true;
    $('load-error').hidden = false;
  });
})();
