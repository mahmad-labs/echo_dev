(() => {
  'use strict';

  document.documentElement.dataset.js = 'enabled';
  const root = document.querySelector('.echo-shell');
  const $ = (selector, context = document) => context.querySelector(selector);
  const $$ = (selector, context = document) => [...context.querySelectorAll(selector)];

  const getCookie = (name) => {
    const item = document.cookie.split('; ').find((row) => row.startsWith(`${name}=`));
    return item ? decodeURIComponent(item.split('=').slice(1).join('=')) : '';
  };

  const icon = (name) => `<svg aria-hidden="true"><use href="/static/icons.svg#${name}"></use></svg>`;

  const showToast = (title, message, type = 'spark', timeout = 5200) => {
    const region = $('#toast-region');
    if (!region) return;
    const toast = document.createElement('article');
    toast.className = 'echo-toast';
    toast.innerHTML = `<span>${icon(type)}</span><div><strong></strong><small></small></div><button type="button" aria-label="Dismiss">${icon('close')}</button>`;
    $('strong', toast).textContent = title;
    $('small', toast).textContent = message;
    $('button', toast).addEventListener('click', () => toast.remove());
    region.append(toast);
    window.setTimeout(() => toast.remove(), timeout);
  };

  const setHidden = (element, hidden) => {
    if (!element) return;
    element.hidden = hidden;
    document.body.style.overflow = hidden ? '' : 'hidden';
  };

  const autoResize = (textarea) => {
    textarea.style.height = 'auto';
    textarea.style.height = `${Math.min(textarea.scrollHeight, 150)}px`;
  };
  $$('textarea').forEach((textarea) => {
    autoResize(textarea);
    textarea.addEventListener('input', () => autoResize(textarea));
  });

  // Appearance initializes before user interaction and remains local to this browser.
  const applyTheme = (value) => {
    let resolved = value;
    if (value === 'system') {
      resolved = window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark';
    }
    document.documentElement.dataset.theme = resolved;
    localStorage.setItem('echo-theme', value);
    $$('[data-theme-value]').forEach((button) => button.classList.toggle('is-active', button.dataset.themeValue === value));
  };
  applyTheme(localStorage.getItem('echo-theme') || 'dark');
  $$('[data-theme-value]').forEach((button) => button.addEventListener('click', () => applyTheme(button.dataset.themeValue)));
  window.matchMedia('(prefers-color-scheme: light)').addEventListener?.('change', () => {
    if ((localStorage.getItem('echo-theme') || 'dark') === 'system') applyTheme('system');
  });

  // Auth form feedback.
  $$('[data-loading-form]').forEach((form) => form.addEventListener('submit', () => {
    const button = $('button[type="submit"]', form);
    if (!button) return;
    button.disabled = true;
    const label = $('span', button);
    if (label) label.textContent = 'Connecting…';
  }));

  if (!root) return;

  const commandPalette = $('#command-palette');
  const paletteInput = $('#palette-input');
  const paletteDefault = $('.palette-default');
  const paletteResults = $('#palette-results');
  const createModal = $('#create-modal');
  const profileMenu = $('#profile-menu');
  const section = root.dataset.section || 'home';
  let searchController;
  let searchTimer;

  const openPalette = (initial = '') => {
    setHidden(commandPalette, false);
    paletteInput.value = initial;
    paletteInput.focus();
    if (initial) runSearch(initial);
  };
  const closePalette = () => setHidden(commandPalette, true);
  $$('.js-open-command').forEach((button) => button.addEventListener('click', () => openPalette()));

  const renderSearchResults = (results, query) => {
    paletteDefault.hidden = true;
    paletteResults.hidden = false;
    paletteResults.innerHTML = '';
    if (!results.length) {
      const ask = document.createElement('button');
      ask.className = 'palette-result is-selected';
      ask.innerHTML = `${icon('spark')}<div><strong></strong><small>Ask Echo using the current workspace context</small></div><kbd>↵</kbd>`;
      $('strong', ask).textContent = `Ask Echo: “${query}”`;
      ask.addEventListener('click', () => {
        closePalette();
        focusComposer(query);
      });
      paletteResults.append(ask);
      return;
    }
    results.forEach((result, index) => {
      const link = document.createElement('a');
      link.className = `palette-result${index === 0 ? ' is-selected' : ''}`;
      link.href = result.url;
      link.innerHTML = `${icon(result.icon || 'search')}<div><strong></strong><small></small></div><kbd>↵</kbd>`;
      $('strong', link).textContent = result.title;
      $('small', link).textContent = `${result.type} · ${result.status}`;
      paletteResults.append(link);
    });
  };

  const runSearch = async (query) => {
    if (query.trim().length < 2) {
      paletteDefault.hidden = false;
      paletteResults.hidden = true;
      return;
    }
    searchController?.abort();
    searchController = new AbortController();
    try {
      const response = await fetch(`${root.dataset.searchUrl}?q=${encodeURIComponent(query.trim())}`, {
        headers: {'X-Requested-With': 'XMLHttpRequest'},
        signal: searchController.signal,
      });
      if (!response.ok) throw new Error('Search is unavailable.');
      const payload = await response.json();
      renderSearchResults(payload.results || [], query.trim());
    } catch (error) {
      if (error.name !== 'AbortError') renderSearchResults([], query.trim());
    }
  };

  paletteInput?.addEventListener('input', () => {
    window.clearTimeout(searchTimer);
    searchTimer = window.setTimeout(() => runSearch(paletteInput.value), 180);
  });
  paletteInput?.addEventListener('keydown', (event) => {
    const results = $$('.palette-result', paletteResults);
    const selected = $('.palette-result.is-selected', paletteResults);
    if (event.key === 'ArrowDown' && results.length) {
      event.preventDefault();
      const index = Math.max(0, results.indexOf(selected));
      results.forEach((item) => item.classList.remove('is-selected'));
      results[(index + 1) % results.length].classList.add('is-selected');
    } else if (event.key === 'ArrowUp' && results.length) {
      event.preventDefault();
      const index = Math.max(0, results.indexOf(selected));
      results.forEach((item) => item.classList.remove('is-selected'));
      results[(index - 1 + results.length) % results.length].classList.add('is-selected');
    } else if (event.key === 'Enter' && selected) {
      event.preventDefault();
      selected.click();
    }
  });

  const openCreate = () => {
    if (!createModal) {
      showToast('Creation follows context', 'Use the command composer to create something in this workspace.');
      return;
    }
    setHidden(createModal, false);
    window.setTimeout(() => $('[name="title"]', createModal)?.focus(), 40);
  };
  const closeCreate = () => setHidden(createModal, true);
  $$('.js-open-create').forEach((button) => button.addEventListener('click', openCreate));
  $$('.js-close-create').forEach((button) => button.addEventListener('click', closeCreate));

  const focusComposer = (text = '') => {
    closePalette();
    const composer = $('#global-command') || $('#hero-command') || $('.js-command-form textarea');
    if (!composer) return;
    composer.value = text || composer.value;
    autoResize(composer);
    composer.focus();
    composer.scrollIntoView({behavior: 'smooth', block: 'center'});
  };
  $$('.js-focus-composer').forEach((button) => button.addEventListener('click', () => focusComposer()));
  $$('.js-use-suggestion').forEach((button) => button.addEventListener('click', () => focusComposer(button.dataset.prompt || button.textContent.trim())));
  $$('.js-palette-suggestion').forEach((button) => button.addEventListener('click', () => focusComposer($('span', button)?.textContent.trim() || '')));

  const setThinking = (thinking) => {
    $$('.presence-mini-orb,.presence-orb').forEach((orb) => orb.classList.toggle('is-thinking', thinking));
    $('.thinking-visual')?.classList.toggle('is-active', thinking);
    const state = $('.presence-header strong');
    if (state) state.textContent = thinking ? 'Thinking' : 'Ready';
  };

  // Computer-use work runs independently and is observed through durable operation records.
  const computerOperationsUrl = root.dataset.computerOperationsUrl || '/api/v1/internet/computer/operations/';
  let computerPollTimer = null;
  const watchedComputerOperations = new Set();

  const operationContent = (operation) => {
    const content = operation?.result?.content;
    if (typeof content === 'string' && content.trim()) return content.trim();
    if (operation?.error) return operation.error;
    if (operation?.attention?.detail) return operation.attention.detail;
    return operation?.current_operation || 'Computer-use operation updated.';
  };

  const buildOperationRow = (operation) => {
    const article = document.createElement('article');
    article.className = `operation-row is-${operation.status || 'queued'}`;
    article.dataset.operationId = operation.id;
    const state = document.createElement('div');
    state.className = 'operation-state';
    state.innerHTML = '<span><i></i></span><small data-operation-status></small>';
    $('[data-operation-status]', state).textContent = String(operation.status || 'queued').replaceAll('_', ' ');
    const copy = document.createElement('div');
    copy.className = 'operation-copy';
    const title = document.createElement('strong'); title.textContent = operation.request || 'Computer-use operation';
    const detail = document.createElement('p'); detail.dataset.operationDetail = ''; detail.textContent = operation.current_operation || operation.error || 'Queued for execution';
    const progress = document.createElement('div');
    progress.className = 'operation-progress'; progress.setAttribute('role', 'progressbar'); progress.setAttribute('aria-label', 'Operation progress'); progress.setAttribute('aria-valuemin', '0'); progress.setAttribute('aria-valuemax', '100'); progress.setAttribute('aria-valuenow', String(operation.progress || 0));
    const bar = document.createElement('i'); bar.style.setProperty('--progress', `${operation.progress || 0}%`); progress.append(bar);
    copy.append(title, detail, progress);
    const actions = document.createElement('div'); actions.className = 'operation-actions';
    if (operation.status === 'waiting_user') {
      const resume = document.createElement('button'); resume.type = 'button'; resume.className = 'secondary-action compact'; resume.dataset.operationResume = operation.id; resume.textContent = 'Resume'; actions.append(resume);
    }
    if (operation.cancellable && !['completed', 'failed', 'cancelled'].includes(operation.status)) {
      const cancel = document.createElement('button'); cancel.type = 'button'; cancel.className = 'icon-button'; cancel.dataset.operationCancel = operation.id; cancel.setAttribute('aria-label', 'Cancel computer-use operation'); cancel.innerHTML = icon('close'); actions.append(cancel);
    }
    article.append(state, copy, actions);
    return article;
  };

  const renderComputerOperations = (operations = []) => {
    const stream = $('[data-operation-stream]');
    if (!stream) return;
    stream.innerHTML = '';
    if (!operations.length) {
      const empty = document.createElement('div'); empty.className = 'operation-empty';
      const strong = document.createElement('strong'); strong.textContent = 'No computer-use operation is running.';
      const p = document.createElement('p'); p.textContent = 'Computer-use work will appear here with verified status and cancellation controls.';
      empty.append(strong, p); stream.append(empty);
    } else operations.slice(0, 20).forEach((operation) => stream.append(buildOperationRow(operation)));
    const activeCount = operations.filter((item) => ['queued', 'running', 'waiting_user', 'cancelling'].includes(item.status)).length;
    const summary = $('[data-operation-summary]'); if (summary) summary.textContent = activeCount ? `${activeCount} active` : 'Ready';
  };

  const fetchComputerOperations = async ({activeOnly = false} = {}) => {
    const suffix = activeOnly ? '?active=true' : '';
    const response = await fetch(`${computerOperationsUrl}${suffix}`, {headers: {'X-Requested-With': 'XMLHttpRequest'}});
    if (!response.ok) throw new Error('Computer-use status is unavailable.');
    const payload = await response.json();
    return payload.operations || [];
  };

  const pollComputerOperations = async () => {
    if (!document.querySelector('[data-computer-use-operations]')) return;
    try { renderComputerOperations(await fetchComputerOperations()); } catch {}
    window.clearTimeout(computerPollTimer);
    computerPollTimer = window.setTimeout(pollComputerOperations, document.hidden ? 9000 : 2500);
  };

  const mutateComputerOperation = async (operationId, action) => {
    const response = await fetch(`${computerOperationsUrl}${operationId}/${action}/`, {
      method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRFToken': getCookie('csrftoken'), 'X-Requested-With': 'XMLHttpRequest'}, body: '{}',
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || `Could not ${action} this operation.`);
    return payload.operation;
  };

  document.addEventListener('click', async (event) => {
    const cancel = event.target.closest('[data-operation-cancel]');
    const resume = event.target.closest('[data-operation-resume]');
    const control = cancel || resume;
    if (!control) return;
    const action = cancel ? 'cancel' : 'resume';
    control.disabled = true;
    try {
      const operation = await mutateComputerOperation(control.dataset.operationCancel || control.dataset.operationResume, action);
      showToast(action === 'cancel' ? 'Cancellation requested' : 'Operation resumed', operation.current_operation || operation.request || 'Echo updated the operation.', action === 'cancel' ? 'alert' : 'spark');
      if (document.querySelector('[data-computer-use-operations]')) renderComputerOperations(await fetchComputerOperations());
    } catch (error) {
      control.disabled = false; showToast('Operation not updated', error.message, 'alert', 8000);
    }
  });

  const appendChatMessage = (role, content) => {
    const stream = $('#chat-message-stream');
    if (!stream) return;
    const article = document.createElement('article');
    article.className = `chat-bubble ${role}`;
    const author = document.createElement('span');
    author.className = 'bubble-author';
    author.textContent = role === 'user' ? 'You' : 'Echo';
    const body = document.createElement('div');
    body.textContent = content;
    const timestamp = document.createElement('small');
    timestamp.textContent = 'Just now';
    article.append(author, body, timestamp);
    stream.append(article);
    article.scrollIntoView({behavior: 'smooth', block: 'end'});
  };

  $$('.js-command-form').forEach((form) => form.addEventListener('submit', async (event) => {
    event.preventDefault();
    const input = $('[name="prompt"]', form);
    const prompt = input?.value.trim();
    if (!prompt) return;
    const submit = $('button[type="submit"]', form);
    submit?.setAttribute('disabled', 'disabled');
    setThinking(true);
    appendChatMessage('user', prompt);
    try {
      const response = await fetch(root.dataset.commandUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': getCookie('csrftoken'),
          'X-Requested-With': 'XMLHttpRequest',
        },
        body: JSON.stringify({prompt, section}),
      });
      const payload = await response.json();
      if (!response.ok) {
        showToast(payload.saved ? 'Command saved' : 'Echo could not continue', payload.detail || 'The request could not be completed.', payload.saved ? 'memory' : 'alert', 8000);
        if (payload.configure_url) {
          const toast = $('.echo-toast:last-child');
          if (toast) toast.addEventListener('click', () => { window.location.href = payload.configure_url; });
        }
      } else {
        appendChatMessage('assistant', payload.content || 'Completed.');
        const homeResult = $('#home-command-result');
        if (homeResult) {
          homeResult.hidden = false;
          homeResult.textContent = payload.content || 'Completed.';
        }
        showToast(payload.status === 'waiting' ? 'Echo needs a next step' : 'Echo responded', payload.latency ? `Reasoning completed in ${payload.latency} ms.` : (payload.content || 'The response is ready.'), payload.status === 'waiting' ? 'alert' : 'spark');
        if (payload.route === 'navigation' && payload.data?.url) window.setTimeout(() => { window.location.href = payload.data.url; }, 450);
        if (payload.data?.operation_id && payload.route === 'computer_use.start') watchComputerUseOperation(payload.data.operation_id, {speak: false});
        if (document.querySelector('[data-computer-use-operations]')) pollComputerOperations();
      }
      input.value = '';
      autoResize(input);
    } catch (error) {
      showToast('Connection interrupted', 'Your command could not reach Echo. Check the server connection.', 'alert', 8000);
    } finally {
      submit?.removeAttribute('disabled');
      setThinking(false);
    }
  }));

  $('[data-create-form]')?.addEventListener('submit', async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const submit = $('button[type="submit"]', form);
    submit.disabled = true;
    try {
      const response = await fetch(form.action, {
        method: 'POST',
        headers: {'X-CSRFToken': getCookie('csrftoken'), 'X-Requested-With': 'XMLHttpRequest'},
        body: new FormData(form),
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || 'Creation failed.');
      closeCreate();
      showToast('Created in Echo', `${payload.record.title} is now part of your workspace.`, 'check-circle');
      window.setTimeout(() => window.location.reload(), 650);
    } catch (error) {
      showToast('Could not create', error.message, 'alert', 7000);
    } finally {
      submit.disabled = false;
    }
  });

  // Real task state changes are persisted through the workspace update endpoint.
  $$('.task-card .task-check').forEach((button) => button.addEventListener('click', async () => {
    const card = button.closest('.task-card');
    const recordId = card?.id.replace('record-', '');
    if (!recordId) return;
    button.disabled = true;
    try {
      const response = await fetch(root.dataset.updateUrl, {
        method: 'POST',
        headers: {'Content-Type': 'application/json', 'X-CSRFToken': getCookie('csrftoken')},
        body: JSON.stringify({section: 'tasks', record_id: recordId, status: 'completed'}),
      });
      if (!response.ok) throw new Error('Task update failed.');
      card.style.opacity = '.45';
      card.style.transform = 'scale(.985)';
      button.style.color = 'var(--success)';
      showToast('Task completed', 'Echo updated the execution queue.', 'check-circle');
    } catch (error) {
      showToast('Could not update task', error.message, 'alert');
    } finally {
      button.disabled = false;
    }
  }));

  const uploadFile = async (file) => {
    const body = new FormData();
    body.append('file', file);
    const response = await fetch(root.dataset.uploadUrl, {
      method: 'POST',
      headers: {'X-CSRFToken': getCookie('csrftoken'), 'X-Requested-With': 'XMLHttpRequest'},
      body,
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || `Could not upload ${file.name}.`);
    return payload.document;
  };

  const handleFiles = async (files) => {
    const list = [...files];
    if (!list.length) return;
    showToast('Adding context', `${list.length} file${list.length === 1 ? '' : 's'} entering the document studio.`, 'upload');
    let succeeded = 0;
    for (const file of list) {
      try {
        await uploadFile(file);
        succeeded += 1;
      } catch (error) {
        showToast('Upload failed', error.message, 'alert', 7000);
      }
    }
    if (succeeded) {
      showToast('Context added', `${succeeded} document${succeeded === 1 ? '' : 's'} securely registered.`, 'check-circle');
      if (section === 'documents') window.setTimeout(() => window.location.reload(), 700);
    }
  };

  const fileInput = $('#document-file');
  const workspaceFileInput = $('#workspace-file-picker');
  const documentDrop = $('.js-document-drop');
  $$('.js-file-picker').forEach((button) => button.addEventListener('click', () => (workspaceFileInput || fileInput)?.click()));
  workspaceFileInput?.addEventListener('change', () => handleFiles(workspaceFileInput.files));
  $$('.js-choose-file').forEach((button) => button.addEventListener('click', () => fileInput?.click()));
  fileInput?.addEventListener('change', () => handleFiles(fileInput.files));
  documentDrop?.addEventListener('click', (event) => {
    if (!event.target.closest('button')) fileInput?.click();
  });
  documentDrop?.addEventListener('keydown', (event) => {
    if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); fileInput?.click(); }
  });
  ['dragenter', 'dragover'].forEach((name) => documentDrop?.addEventListener(name, (event) => {
    event.preventDefault(); documentDrop.classList.add('is-dragover');
  }));
  ['dragleave', 'drop'].forEach((name) => documentDrop?.addEventListener(name, (event) => {
    event.preventDefault(); documentDrop.classList.remove('is-dragover');
  }));
  documentDrop?.addEventListener('drop', (event) => handleFiles(event.dataTransfer.files));

  const dropOverlay = $('#drop-overlay');
  let dragDepth = 0;
  document.addEventListener('dragenter', (event) => {
    if (![...event.dataTransfer.types].includes('Files')) return;
    dragDepth += 1;
    setHidden(dropOverlay, false);
  });
  document.addEventListener('dragleave', () => {
    dragDepth -= 1;
    if (dragDepth <= 0) { dragDepth = 0; setHidden(dropOverlay, true); }
  });
  document.addEventListener('dragover', (event) => event.preventDefault());
  document.addEventListener('drop', (event) => {
    event.preventDefault();
    dragDepth = 0;
    setHidden(dropOverlay, true);
    if (event.dataTransfer.files.length) handleFiles(event.dataTransfer.files);
  });

  // Echo Voice lifecycle is server-authoritative. The browser owns only ephemeral
  // capture/playback resources; VoiceSession.state owns wake/active/processing/speaking/shutdown.
  const VoiceRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  const voiceConsole = $('#voice-console');
  const voiceEndpoints = {
    capabilities: root.dataset.voiceCapabilitiesUrl,
    runtime: root.dataset.voiceRuntimeUrl || '/api/v1/voice/runtime/',
    profile: root.dataset.voiceProfileUrl,
    sessions: root.dataset.voiceSessionsUrl,
    transcript: root.dataset.voiceTranscriptUrl,
    audio: root.dataset.voiceAudioUrl,
    synthesis: root.dataset.voiceSynthesisUrl,
    speaker: root.dataset.voiceSpeakerUrl,
    speakerEnroll: root.dataset.voiceSpeakerEnrollUrl,
    privacy: root.dataset.voicePrivacyUrl,
  };
  const VOICE_CAPTURE_STATES = new Set(['wake_word_listening', 'active_session']);
  const voiceRuntime = {
    initialized: false,
    profile: null,
    providers: [],
    session: null,
    permission: 'unknown',
    recognition: null,
    recorder: null,
    stream: null,
    chunks: [],
    processing: false,
    restartTimer: null,
    clockTimer: null,
    runtimePollTimer: null,
    activeAudio: null,
    utterance: null,
    requestController: null,
    speakerContext: null,
    speakerTimer: null,
    speakerAccumulator: null,
    speakerFrames: 0,
    speechDetected: false,
    previousFocus: null,
    currentOperationId: null,
    currentAgentTaskId: null,
    greetingInProgress: false,
    initializingPromise: null,
  };

  const voiceStateCopy = {
    starting: ['Starting', 'Initializing Echo Voice', 'Starting voice…'],
    greeting: ['Greeting', 'Echo is introducing itself', 'Hello. I’m Echo.'],
    disabled: ['Disabled', 'Voice command listening is disabled', 'Voice is disabled'],
    wake_word_listening: ['Listening for “Echo”', 'Wake-word microphone active', 'Say “Echo” to begin'],
    active_session: ['Active', 'Echo is listening for commands', 'I’m listening…'],
    processing: ['Processing', 'Echo is processing your request', 'Working on that…'],
    speaking: ['Speaking', 'Echo is speaking', 'Echo is responding…'],
    sleeping: ['Sleeping', 'Echo is waiting in low-activity mode', 'Say “Echo” when ready'],
    shutdown: ['Shutdown', 'Voice resources are released', 'Voice is shut down'],
    error: ['Error', 'Voice needs attention', 'Voice encountered a problem'],
  };

  const voiceCapabilities = () => ({
    speech_recognition: Boolean(VoiceRecognition),
    speech_synthesis: Boolean(window.speechSynthesis && window.SpeechSynthesisUtterance),
    media_recorder: Boolean(window.MediaRecorder),
    media_devices: Boolean(navigator.mediaDevices?.getUserMedia),
    secure_context: Boolean(window.isSecureContext),
  });

  const voiceFetch = async (url, options = {}) => {
    const headers = new Headers(options.headers || {});
    headers.set('X-Requested-With', 'XMLHttpRequest');
    if (!(options.body instanceof FormData)) headers.set('Content-Type', 'application/json');
    if (!['GET', 'HEAD'].includes((options.method || 'GET').toUpperCase())) headers.set('X-CSRFToken', getCookie('csrftoken'));
    const response = await fetch(url, {...options, headers});
    let payload = {};
    try { payload = await response.json(); } catch { payload = {}; }
    if (!response.ok) {
      const error = new Error(payload.detail || 'Voice request failed.');
      error.code = payload.code || 'voice_request_failed';
      error.status = response.status;
      throw error;
    }
    return payload;
  };

  const setVoiceText = (selector, value) => $$(selector).forEach((node) => { node.textContent = value; });
  const currentVoiceState = () => voiceRuntime.session?.state || 'starting';
  const voiceIsShutdown = () => currentVoiceState() === 'shutdown';
  const voiceCanCapture = () => VOICE_CAPTURE_STATES.has(currentVoiceState()) && !voiceRuntime.processing && !voiceRuntime.greetingInProgress;
  const resumeState = () => voiceRuntime.session?.mode === 'active' ? 'active_session' : 'wake_word_listening';

  const formatVoiceRemaining = (seconds) => {
    const total = Math.max(0, Math.floor(Number(seconds || 0)));
    return `${String(Math.floor(total / 60)).padStart(2, '0')}:${String(total % 60).padStart(2, '0')}`;
  };

  const renderVoiceState = (detail = '') => {
    const state = currentVoiceState();
    root.dataset.voiceState = state;
    const [label, microphone, prompt] = voiceStateCopy[state] || [state.replaceAll('_', ' '), '', 'Talk to Echo'];
    setVoiceText('[data-voice-state-label]', label);
    setVoiceText('[data-microphone-status]', detail || microphone);
    setVoiceText('[data-voice-guidance]', detail || microphone);
    setVoiceText('[data-voice-prompt]', prompt);
    $$('[data-voice-visual-state]').forEach((node) => { node.dataset.voiceVisualState = state; });
    $$('.js-voice-toggle').forEach((button) => {
      button.disabled = state === 'processing' || state === 'speaking';
      button.classList.toggle('is-active', state === 'active_session');
      button.setAttribute('aria-label', voiceIsShutdown() ? 'Restart and activate voice' : 'Activate voice');
    });
    $$('.js-voice-disable,.js-voice-pause').forEach((button) => { button.disabled = !voiceRuntime.session || ['shutdown', 'wake_word_listening'].includes(state); });
    $$('.js-voice-shutdown,.js-voice-stop').forEach((button) => { button.disabled = !voiceRuntime.session || state === 'shutdown'; });
    updateVoiceSessionMeta();
    updateVoiceReadiness();
  };

  const applyVoiceSession = (session, detail = '') => {
    if (!session) return;
    voiceRuntime.session = session;
    if (session.profile) voiceRuntime.profile = {...(voiceRuntime.profile || {}), ...session.profile};
    if (session.permission) voiceRuntime.permission = session.permission;
    renderVoiceState(detail);
  };

  const updateVoiceSessionMeta = () => {
    const session = voiceRuntime.session;
    const state = session?.state || 'starting';
    setVoiceText('[data-voice-mode]', state === 'active_session' || session?.mode === 'active' ? 'Active session' : state === 'shutdown' ? 'Shutdown' : 'Wake-word mode');
    if (session?.mode === 'active' && session.active_expires_at) {
      const remaining = Math.max(0, Math.floor((new Date(session.active_expires_at).getTime() - Date.now()) / 1000));
      setVoiceText('[data-voice-session-timer]', `${formatVoiceRemaining(remaining)} / 60:00 inactivity window`);
    } else if (state === 'shutdown') setVoiceText('[data-voice-session-timer]', 'Voice shut down');
    else setVoiceText('[data-voice-session-timer]', `Say ${session?.wake_word || 'Echo'} to begin`);
    const speaker = session?.speaker_state || (voiceRuntime.profile?.speaker_identification_enabled ? 'not_enrolled' : 'disabled');
    setVoiceText('[data-voice-speaker-state]', ({recognized: 'Recognized', unrecognized: 'Not recognized', not_enrolled: 'Not enrolled', disabled: 'Disabled', unknown: 'Unknown'})[speaker] || String(speaker).replaceAll('_', ' '));
    setVoiceText('[data-readiness-session]', session ? `${session.turn_count || 0} turns · ${state.replaceAll('_', ' ')}` : 'Not started');
  };

  const providerReady = (identifier, capability) => voiceRuntime.providers.some((item) => (
    item.identifier === identifier && item[capability] && (!item.requires_configuration || item.configured)
  ));

  const updateVoiceReadiness = () => {
    const caps = voiceCapabilities();
    const profile = voiceRuntime.profile || {};
    const sttReady = profile.speech_to_text_provider === 'browser' ? caps.speech_recognition : providerReady(profile.speech_to_text_provider, 'speech_to_text');
    const ttsReady = profile.text_to_speech_provider === 'browser' ? caps.speech_synthesis : providerReady(profile.text_to_speech_provider, 'text_to_speech');
    setVoiceText('[data-readiness-microphone]', voiceRuntime.permission === 'granted' ? 'Allowed' : voiceRuntime.permission === 'denied' ? 'Blocked' : caps.media_devices ? 'Not requested' : 'Unavailable');
    setVoiceText('[data-readiness-stt]', sttReady ? 'Ready' : 'Unavailable / not configured');
    setVoiceText('[data-readiness-tts]', ttsReady ? 'Ready' : 'Unavailable / not configured');
    setVoiceText('[data-voice-runtime-status]', caps.media_devices && sttReady ? 'Ready' : 'Configuration needed');
  };

  const reportVoiceState = async (state, detail = '', errorCode = '', permission = '') => {
    if (!voiceRuntime.session || voiceIsShutdown()) return voiceRuntime.session;
    const payload = await voiceFetch(`${voiceEndpoints.sessions}${voiceRuntime.session.id}/state/`, {
      method: 'POST',
      body: JSON.stringify({state, detail, error_code: errorCode, permission, browser_capabilities: voiceCapabilities()}),
    });
    applyVoiceSession(payload.session, detail);
    return payload.session;
  };

  const refreshVoiceRuntime = async () => {
    const payload = await voiceFetch(`${voiceEndpoints.runtime}?client_session_id=${encodeURIComponent(sessionStorage.getItem('echoVoiceClientId') || '')}`);
    applyVoiceSession(payload.session);
    return payload.session;
  };

  const detectPermission = async () => {
    if (!navigator.mediaDevices?.getUserMedia) { voiceRuntime.permission = 'unavailable'; return; }
    if (!navigator.permissions?.query) { voiceRuntime.permission = 'unknown'; return; }
    try {
      const status = await navigator.permissions.query({name: 'microphone'});
      voiceRuntime.permission = status.state || 'unknown';
      status.onchange = () => {
        voiceRuntime.permission = status.state || 'unknown';
        updateVoiceReadiness();
        if (status.state === 'denied') stopCapture({release: true});
        else if (status.state === 'granted' && voiceCanCapture()) scheduleCapture(50);
      };
    } catch { voiceRuntime.permission = 'unknown'; }
  };

  const cleanupSpeakerFingerprint = () => {
    if (voiceRuntime.speakerTimer) clearInterval(voiceRuntime.speakerTimer);
    voiceRuntime.speakerTimer = null;
    try { voiceRuntime.speakerContext?.close?.(); } catch {}
    voiceRuntime.speakerContext = null;
  };

  const startSpeakerFingerprint = (stream) => {
    cleanupSpeakerFingerprint();
    voiceRuntime.speakerAccumulator = new Array(12).fill(0);
    voiceRuntime.speakerFrames = 0;
    try {
      const AudioContext = window.AudioContext || window.webkitAudioContext;
      if (!AudioContext) return;
      const context = new AudioContext();
      const analyser = context.createAnalyser();
      analyser.fftSize = 1024;
      context.createMediaStreamSource(stream).connect(analyser);
      const values = new Uint8Array(analyser.frequencyBinCount);
      voiceRuntime.speakerContext = context;
      voiceRuntime.speakerTimer = setInterval(() => {
        analyser.getByteFrequencyData(values);
        for (let band = 0; band < 12; band += 1) {
          const start = Math.floor((band / 12) * values.length);
          const end = Math.max(start + 1, Math.floor(((band + 1) / 12) * values.length));
          let sum = 0;
          for (let i = start; i < end; i += 1) sum += values[i];
          voiceRuntime.speakerAccumulator[band] += sum / (end - start) / 255;
        }
        voiceRuntime.speakerFrames += 1;
      }, 120);
    } catch {}
  };

  const takeSpeakerFingerprint = () => {
    const frames = voiceRuntime.speakerFrames || 0;
    const embedding = frames && voiceRuntime.speakerAccumulator ? voiceRuntime.speakerAccumulator.map((value) => value / frames) : [];
    cleanupSpeakerFingerprint();
    voiceRuntime.speakerAccumulator = null;
    voiceRuntime.speakerFrames = 0;
    return embedding;
  };

  const releaseMicrophone = () => {
    takeSpeakerFingerprint();
    voiceRuntime.stream?.getTracks?.().forEach((track) => track.stop());
    voiceRuntime.stream = null;
  };

  const requestMicrophone = async () => {
    if (!window.isSecureContext && !['localhost', '127.0.0.1'].includes(window.location.hostname)) throw new Error('Microphone access requires HTTPS or localhost.');
    if (!navigator.mediaDevices?.getUserMedia) throw new Error('This browser does not provide microphone access.');
    try {
      const stream = await navigator.mediaDevices.getUserMedia({audio: {echoCancellation: true, noiseSuppression: true, autoGainControl: true}, video: false});
      voiceRuntime.permission = 'granted';
      voiceRuntime.stream = stream;
      startSpeakerFingerprint(stream);
      updateVoiceReadiness();
      if (voiceRuntime.session) reportVoiceState(currentVoiceState(), '', '', 'granted').catch(() => {});
      return stream;
    } catch (error) {
      voiceRuntime.permission = ['NotAllowedError', 'SecurityError'].includes(error.name) ? 'denied' : 'unavailable';
      if (voiceRuntime.session && !voiceIsShutdown()) reportVoiceState('error', error.message, 'microphone_unavailable', voiceRuntime.permission).catch(() => {});
      throw new Error(voiceRuntime.permission === 'denied' ? 'Microphone permission was denied. Allow it in browser settings and try again.' : `Microphone unavailable: ${error.message}`);
    }
  };

  const stopSpeech = () => {
    if (voiceRuntime.activeAudio) { voiceRuntime.activeAudio.pause(); voiceRuntime.activeAudio.currentTime = 0; voiceRuntime.activeAudio = null; }
    if (window.speechSynthesis) window.speechSynthesis.cancel();
    voiceRuntime.utterance = null;
  };

  const stopCapture = ({release = true} = {}) => {
    if (voiceRuntime.restartTimer) clearTimeout(voiceRuntime.restartTimer);
    voiceRuntime.restartTimer = null;
    if (voiceRuntime.recognition) { try { voiceRuntime.recognition.abort(); } catch {} voiceRuntime.recognition = null; }
    if (voiceRuntime.recorder && voiceRuntime.recorder.state !== 'inactive') { try { voiceRuntime.recorder.stop(); } catch {} }
    voiceRuntime.recorder = null;
    if (release) releaseMicrophone();
  };

  const scheduleCapture = (delay = 200) => {
    if (voiceRuntime.restartTimer) clearTimeout(voiceRuntime.restartTimer);
    if (!voiceCanCapture() || document.hidden) return;
    voiceRuntime.restartTimer = setTimeout(() => {
      voiceRuntime.restartTimer = null;
      startCapture().catch((error) => {
        renderVoiceState(error.message);
        if (!['NotAllowedError', 'SecurityError'].includes(error.name) && voiceCanCapture()) scheduleCapture(900);
      });
    }, delay);
  };

  const stripWakeWord = (text) => String(text || '').replace(/^\s*(?:hey\s+)?echo\b[\s,.:;!?-]*/i, '').trim();
  const containsWakeWord = (text) => /^\s*(?:hey\s+)?echo\b/i.test(String(text || ''));

  const appendVoiceTurn = (role, content, meta = {}) => {
    if (!content) return;
    $$('[data-voice-turn-stream]').forEach((stream) => {
      const item = document.createElement('article');
      item.className = `voice-turn is-${role}`;
      const label = document.createElement('span'); label.textContent = role === 'assistant' ? 'Echo' : 'You';
      const body = document.createElement('p'); body.textContent = content;
      item.append(label, body);
      if (meta.route) { const route = document.createElement('small'); route.textContent = meta.route; item.appendChild(route); }
      stream.appendChild(item); stream.scrollTop = stream.scrollHeight;
    });
  };

  const renderVoiceSession = (session) => {
    applyVoiceSession(session);
    const turns = [];
    (session.transcripts || []).forEach((item) => turns.push({at: item.created_at, role: 'user', content: item.text, route: item.command_route}));
    (session.syntheses || []).forEach((item) => turns.push({at: item.created_at, role: 'assistant', content: item.text}));
    turns.sort((a, b) => String(a.at).localeCompare(String(b.at)));
    $$('[data-voice-turn-stream]').forEach((stream) => { stream.innerHTML = ''; });
    turns.forEach((turn) => appendVoiceTurn(turn.role, turn.content, {route: turn.route}));
  };

  const recoverCaptureState = async (detail = '') => {
    if (!voiceRuntime.session || voiceIsShutdown()) return;
    try { await reportVoiceState(resumeState(), detail); } catch {}
    scheduleCapture(180);
  };

  const completeSpeechPlayback = async (synthesisId = '', outcome = 'completed') => {
    if (!voiceRuntime.session || voiceIsShutdown()) return;
    try {
      const payload = await voiceFetch(`${voiceEndpoints.sessions}${voiceRuntime.session.id}/speech-complete/`, {
        method: 'POST',
        body: JSON.stringify({synthesis_id: synthesisId || '', outcome}),
      });
      if (payload.session) applyVoiceSession(payload.session);
      if (voiceRuntime.permission === 'granted' && voiceCanCapture()) scheduleCapture(120);
    } catch {
      await recoverCaptureState();
    }
  };

  const speakWithBrowser = (text, synthesis = {}) => new Promise((resolve) => {
    if (!text || !window.speechSynthesis || !window.SpeechSynthesisUtterance) { recoverCaptureState().finally(resolve); return; }
    stopCapture({release: true});
    stopSpeech();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = synthesis.language || voiceRuntime.profile?.language || 'en-US';
    utterance.rate = Number(synthesis.data?.rate || voiceRuntime.profile?.speaking_rate || 1);
    utterance.pitch = Number(synthesis.data?.pitch || voiceRuntime.profile?.pitch || 1);
    utterance.volume = Number(synthesis.data?.volume || voiceRuntime.profile?.volume || 1);
    voiceRuntime.utterance = utterance;
    utterance.onstart = () => renderVoiceState('Echo is speaking.');
    let finished = false;
    const finish = async (event) => {
      if (finished) return;
      finished = true;
      voiceRuntime.utterance = null;
      await completeSpeechPlayback(synthesis?.id || '', event?.type === 'error' ? 'error' : 'completed');
      resolve();
    };
    utterance.onend = finish;
    utterance.onerror = finish;
    try { window.speechSynthesis.speak(utterance); } catch { finish({type: 'error'}); }
  });

  const playServerAudio = (synthesis) => new Promise((resolve) => {
    if (!synthesis?.audio_url) { recoverCaptureState().finally(resolve); return; }
    stopCapture({release: true});
    stopSpeech();
    const audio = new Audio(synthesis.audio_url);
    voiceRuntime.activeAudio = audio;
    let finished = false;
    const finish = async (event) => {
      if (finished) return;
      finished = true;
      voiceRuntime.activeAudio = null;
      await completeSpeechPlayback(synthesis?.id || '', event?.type === 'error' ? 'error' : 'completed');
      resolve();
    };
    audio.onended = finish; audio.onerror = finish;
    audio.play().catch(() => finish({type: 'error'}));
  });

  const watchComputerUseOperation = (operationId, {speak = false} = {}) => {
    if (!operationId || watchedComputerOperations.has(operationId)) return;
    watchedComputerOperations.add(operationId);
    voiceRuntime.currentOperationId = operationId;
    const check = async () => {
      try {
        const response = await fetch(`${computerOperationsUrl}${operationId}/`, {headers: {'X-Requested-With': 'XMLHttpRequest'}});
        if (!response.ok) throw new Error('Operation status is unavailable.');
        const payload = await response.json(); const operation = payload.operation || {};
        setVoiceText('[data-current-operation]', operation.current_operation || operation.status || 'Working');
        setVoiceText('[data-current-tool]', operation.current_tool || 'computer-use');
        if (['queued', 'running', 'cancelling'].includes(operation.status)) { setTimeout(check, document.hidden ? 5000 : 1600); return; }
        watchedComputerOperations.delete(operationId);
        if (voiceRuntime.currentOperationId === operationId) voiceRuntime.currentOperationId = null;
        const content = operationContent(operation);
        appendVoiceTurn('assistant', content, {route: `computer_use.${operation.status}`});
        if (speak && operation.status === 'completed' && !voiceIsShutdown()) await speakWithBrowser(content);
        else showToast(operation.status === 'completed' ? 'Computer task completed' : 'Computer task needs attention', content, operation.status === 'completed' ? 'check-circle' : 'alert', 9000);
      } catch { if (watchedComputerOperations.has(operationId)) setTimeout(check, 3000); }
    };
    setTimeout(check, 600);
  };

  const deliverVoiceResponse = async (payload) => {
    if (payload.session) applyVoiceSession(payload.session);
    if (payload.ignored) {
      if (payload.reason === 'speaker_unrecognized') showToast('Command ignored', payload.detail || 'Speaker not recognized.', 'alert');
      await recoverCaptureState(payload.detail || ''); return;
    }
    const transcript = payload.transcript || {}; const response = payload.response || {}; const command = response.command || {};
    setVoiceText('[data-live-transcript]', transcript.text || 'Nothing heard yet.');
    appendVoiceTurn('user', transcript.text || '', {route: transcript.command_route});
    appendVoiceTurn('assistant', response.content || 'Completed.', {route: response.route});
    const data = command.data || {};
    setVoiceText('[data-current-agent]', String(data.agent || data.agent_identifier || response.route?.split('.')?.[0] || 'Echo').replaceAll('_', ' '));
    voiceRuntime.currentAgentTaskId = data.parent_agent_task_id || data.agent_task_id || null;
    setVoiceText('[data-current-task]', String(voiceRuntime.currentAgentTaskId || 'None').slice(0, 14));
    setVoiceText('[data-current-tool]', String(data.current_tool || (data.operation_id ? 'computer-use' : 'None')).replaceAll('_', ' '));
    setVoiceText('[data-current-operation]', String(data.current_operation || data.execution_status || 'Response ready').replaceAll('_', ' '));
    if (data.operation_id && ['running', 'queued'].includes(data.execution_status)) watchComputerUseOperation(data.operation_id, {speak: true});
    if (payload.synthesis_error) { showToast('Speech output unavailable', payload.synthesis_error, 'alert'); await recoverCaptureState(); return; }
    if (!payload.should_speak || !payload.synthesis || currentVoiceState() === 'shutdown') { scheduleCapture(120); return; }
    if (payload.synthesis.provider === 'browser') await speakWithBrowser(response.content, payload.synthesis);
    else await playServerAudio(payload.synthesis);
  };

  const submitVoiceTranscript = async (text, {provider = 'browser', confidence = 1, language = '', speakerEmbedding = []} = {}) => {
    if (voiceRuntime.processing) return;
    const transcript = String(text || '').trim(); if (!transcript) { scheduleCapture(100); return; }
    if (provider !== 'typed' && currentVoiceState() === 'wake_word_listening' && !containsWakeWord(transcript)) { scheduleCapture(120); return; }
    voiceRuntime.processing = true; stopCapture({release: true});
    setVoiceText('[data-live-transcript]', transcript);
    voiceRuntime.requestController = new AbortController();
    try {
      await reportVoiceState('processing', 'Processing what I heard…');
      const payload = await voiceFetch(voiceEndpoints.transcript, {
        method: 'POST', signal: voiceRuntime.requestController.signal,
        body: JSON.stringify({session_id: voiceRuntime.session.id, text: transcript, provider, confidence, language: language || voiceRuntime.session.language || 'en-US', is_final: true, speaker_embedding: speakerEmbedding || []}),
      });
      await deliverVoiceResponse(payload);
    } catch (error) {
      if (error.name !== 'AbortError') { showToast('Voice command failed', error.message, 'alert', 8000); await recoverCaptureState(error.message); }
    } finally { voiceRuntime.requestController = null; voiceRuntime.processing = false; }
  };

  const submitRecordedAudio = async (blob, speakerEmbedding = []) => {
    if (!blob?.size || voiceRuntime.processing) { scheduleCapture(120); return; }
    voiceRuntime.processing = true; voiceRuntime.requestController = new AbortController();
    try { await reportVoiceState('processing', 'Processing recorded speech…'); } catch {}
    const body = new FormData(); body.append('session_id', voiceRuntime.session.id); body.append('audio', blob, 'echo-recording.webm');
    if (speakerEmbedding.length) body.append('speaker_embedding', JSON.stringify(speakerEmbedding));
    try { const payload = await voiceFetch(voiceEndpoints.audio, {method: 'POST', signal: voiceRuntime.requestController.signal, body}); await deliverVoiceResponse(payload); }
    catch (error) { if (error.name !== 'AbortError') { showToast('Transcription failed', error.message, 'alert'); await recoverCaptureState(error.message); } }
    finally { voiceRuntime.requestController = null; voiceRuntime.processing = false; releaseMicrophone(); }
  };

  const startBrowserRecognition = () => {
    const recognition = new VoiceRecognition();
    recognition.lang = voiceRuntime.profile?.language || 'en-US'; recognition.continuous = false; recognition.interimResults = true; recognition.maxAlternatives = 1;
    voiceRuntime.recognition = recognition;
    let finalReceived = false;
    recognition.onresult = (event) => {
      let interim = '';
      for (let i = event.resultIndex; i < event.results.length; i += 1) {
        const result = event.results[i]; const text = result[0]?.transcript || '';
        if (result.isFinal) {
          finalReceived = true; const embedding = takeSpeakerFingerprint();
          try { recognition.abort(); } catch {} voiceRuntime.recognition = null; releaseMicrophone();
          submitVoiceTranscript(text, {provider: 'browser', confidence: result[0]?.confidence || 0, language: recognition.lang, speakerEmbedding: embedding});
          return;
        }
        interim += text;
      }
      if (interim) setVoiceText('[data-live-transcript]', interim);
    };
    recognition.onerror = (event) => {
      const code = event.error || 'recognition_error';
      if (['not-allowed', 'service-not-allowed'].includes(code)) {
        voiceRuntime.permission = 'denied'; stopCapture({release: true});
        reportVoiceState('error', 'Microphone or speech recognition permission was denied.', 'permission_denied', 'denied').catch(() => {});
        showToast('Voice permission required', 'Allow microphone and speech recognition access in your browser.', 'alert'); return;
      }
      if (!['no-speech', 'aborted'].includes(code)) setVoiceText('[data-microphone-status]', `Speech recognition interrupted: ${code}`);
    };
    recognition.onend = () => {
      if (voiceRuntime.recognition === recognition) voiceRuntime.recognition = null;
      if (!finalReceived) releaseMicrophone();
      if (!finalReceived && voiceCanCapture()) scheduleCapture(180);
    };
    recognition.start();
  };

  const startServerRecorder = (stream) => {
    const mime = ['audio/webm;codecs=opus', 'audio/webm', 'audio/ogg;codecs=opus'].find((value) => window.MediaRecorder?.isTypeSupported?.(value)) || '';
    const recorder = mime ? new MediaRecorder(stream, {mimeType: mime}) : new MediaRecorder(stream);
    voiceRuntime.recorder = recorder; voiceRuntime.chunks = []; voiceRuntime.speechDetected = false;
    const startedAt = performance.now(); let lastSpeechAt = 0; let vadTimer = null; let vadContext = null;
    recorder.ondataavailable = (event) => { if (event.data?.size) voiceRuntime.chunks.push(event.data); };
    recorder.onstart = () => {
      try {
        const AudioContext = window.AudioContext || window.webkitAudioContext; if (!AudioContext) return;
        vadContext = new AudioContext(); const analyser = vadContext.createAnalyser(); analyser.fftSize = 1024; vadContext.createMediaStreamSource(stream).connect(analyser); const values = new Uint8Array(analyser.fftSize);
        vadTimer = setInterval(() => {
          analyser.getByteTimeDomainData(values); let energy = 0;
          values.forEach((value) => { const n = (value - 128) / 128; energy += n * n; });
          const rms = Math.sqrt(energy / values.length); const now = performance.now();
          if (rms > 0.025) { voiceRuntime.speechDetected = true; lastSpeechAt = now; }
          if (voiceRuntime.speechDetected && now - lastSpeechAt > 1050) { try { recorder.stop(); } catch {} }
          else if (!voiceRuntime.speechDetected && now - startedAt > 8000) { try { recorder.stop(); } catch {} }
        }, 100);
      } catch {}
    };
    recorder.onstop = () => {
      if (vadTimer) clearInterval(vadTimer); try { vadContext?.close?.(); } catch {}
      const embedding = takeSpeakerFingerprint(); const hadSpeech = voiceRuntime.speechDetected;
      const blob = new Blob(voiceRuntime.chunks, {type: recorder.mimeType || 'audio/webm'});
      voiceRuntime.recorder = null; voiceRuntime.chunks = []; releaseMicrophone();
      if (hadSpeech) submitRecordedAudio(blob, embedding); else scheduleCapture(140);
    };
    recorder.onerror = () => { if (vadTimer) clearInterval(vadTimer); releaseMicrophone(); scheduleCapture(800); };
    recorder.start(250);
  };

  async function startCapture() {
    if (!voiceCanCapture() || voiceRuntime.recognition || voiceRuntime.recorder || voiceRuntime.stream) return;
    const provider = voiceRuntime.profile?.speech_to_text_provider || 'browser';
    if (provider === 'browser' && !VoiceRecognition) throw new Error('Browser speech recognition is unavailable. Select a configured STT provider.');
    if (provider !== 'browser' && !providerReady(provider, 'speech_to_text')) throw new Error('The selected speech-to-text provider is not configured.');
    const stream = await requestMicrophone();
    if (!voiceCanCapture()) { releaseMicrophone(); return; }
    if (provider === 'browser') startBrowserRecognition(); else if (window.MediaRecorder) startServerRecorder(stream); else { releaseMicrophone(); throw new Error('This browser cannot record audio for the configured STT provider.'); }
  }

  const speakStartupGreeting = async () => {
    if (!voiceRuntime.session?.greeting_pending || voiceRuntime.greetingInProgress) return;
    voiceRuntime.greetingInProgress = true;
    const text = voiceRuntime.session.greeting || "Hello. I'm Echo. I'm ready when you are.";
    // Persist the one-time greeting marker before audio starts. A reload can no longer
    // create a second greeting/microphone loop if the page closes mid-utterance.
    try {
      const marked = await voiceFetch(`${voiceEndpoints.sessions}${voiceRuntime.session.id}/greeted/`, {method: 'POST', body: '{}'});
      applyVoiceSession(marked.session);
    } catch (error) {
      voiceRuntime.greetingInProgress = false;
      throw error;
    }
    appendVoiceTurn('assistant', text, {route: 'voice.greeting'});
    if (!window.speechSynthesis || !window.SpeechSynthesisUtterance) {
      voiceRuntime.greetingInProgress = false;
      if (voiceRuntime.permission === 'granted') scheduleCapture(100);
      return;
    }
    stopCapture({release: true});
    try { await reportVoiceState('speaking', 'Echo is greeting you.'); } catch {}
    const utterance = new SpeechSynthesisUtterance(text); utterance.lang = voiceRuntime.profile?.language || 'en-US'; voiceRuntime.utterance = utterance;
    let finished = false;
    const finish = async (event) => {
      if (finished) return;
      finished = true;
      voiceRuntime.utterance = null; voiceRuntime.greetingInProgress = false;
      await completeSpeechPlayback('', event?.type === 'error' ? 'error' : 'completed');
    };
    utterance.onend = finish; utterance.onerror = finish;
    try { window.speechSynthesis.speak(utterance); } catch { finish({type: 'error'}); }
  };

  const initializeVoice = async () => {
    if (voiceRuntime.initialized) return;
    if (voiceRuntime.initializingPromise) return voiceRuntime.initializingPromise;
    voiceRuntime.initializingPromise = (async () => {
      try {
        const caps = await voiceFetch(voiceEndpoints.capabilities); voiceRuntime.profile = caps.profile; voiceRuntime.providers = caps.providers || [];
        await detectPermission();
        if (!sessionStorage.getItem('echoVoiceClientId')) sessionStorage.setItem('echoVoiceClientId', crypto.randomUUID?.() || `${Date.now()}-${Math.random()}`);
        await refreshVoiceRuntime();
        try { const speaker = await voiceFetch(voiceEndpoints.speaker); voiceRuntime.speakerProfile = speaker.speaker; } catch {}
        voiceRuntime.initialized = true;
        if (voiceRuntime.session?.greeting_pending) await speakStartupGreeting();
        else if (voiceRuntime.permission === 'granted' && voiceCanCapture()) scheduleCapture(80);
        startVoiceClock();
      } catch (error) { showToast('Voice initialization failed', error.message, 'alert', 9000); }
      finally { voiceRuntime.initializingPromise = null; }
    })();
    return voiceRuntime.initializingPromise;
  };

  const startVoiceClock = () => {
    if (voiceRuntime.clockTimer) clearInterval(voiceRuntime.clockTimer);
    voiceRuntime.clockTimer = setInterval(() => {
      updateVoiceSessionMeta();
      if (voiceRuntime.session?.mode === 'active' && voiceRuntime.session.active_expires_at && new Date(voiceRuntime.session.active_expires_at).getTime() <= Date.now()) {
        const expiredSessionId = voiceRuntime.session.id;
        refreshVoiceRuntime().then(async (session) => {
          if (session?.id === expiredSessionId && session.state === 'wake_word_listening') {
            const message = `I'll wait for you to say ${session.wake_word || 'Echo'}.`;
            appendVoiceTurn('assistant', message, {route: 'voice.inactivity_timeout'});
            if (window.speechSynthesis && window.SpeechSynthesisUtterance) {
              try { await reportVoiceState('speaking', 'Echo is announcing the inactivity timeout.'); } catch {}
              await speakWithBrowser(message, {language: session.language || voiceRuntime.profile?.language || 'en-US'});
            } else scheduleCapture(80);
          } else scheduleCapture(80);
        }).catch(() => {});
      }
    }, 1000);
    if (voiceRuntime.runtimePollTimer) clearInterval(voiceRuntime.runtimePollTimer);
    voiceRuntime.runtimePollTimer = setInterval(() => { if (!document.hidden && voiceRuntime.session && !voiceIsShutdown()) refreshVoiceRuntime().catch(() => {}); }, 20000);
  };

  const activateVoice = async () => {
    await initializeVoice();
    if (voiceIsShutdown()) await refreshVoiceRuntime();
    if (!voiceRuntime.session || voiceIsShutdown()) { const payload = await voiceFetch(voiceEndpoints.sessions, {method: 'POST', body: JSON.stringify({client_session_id: sessionStorage.getItem('echoVoiceClientId'), input_mode: 'mixed'})}); applyVoiceSession(payload.session); }
    stopSpeech(); stopCapture({release: true});
    try {
      const payload = await voiceFetch(`${voiceEndpoints.sessions}${voiceRuntime.session.id}/activate/`, {method: 'POST', body: '{}'}); applyVoiceSession(payload.session, 'Active voice session started.');
      await startCapture();
    } catch (error) { showToast('Voice could not activate', error.message, 'alert'); renderVoiceState(error.message); }
  };

  const disableVoice = async () => {
    if (!voiceRuntime.session || voiceIsShutdown()) return;
    voiceRuntime.requestController?.abort?.(); stopSpeech(); stopCapture({release: true});
    try { const payload = await voiceFetch(`${voiceEndpoints.sessions}${voiceRuntime.session.id}/disable/`, {method: 'POST', body: '{}'}); applyVoiceSession(payload.session, `Waiting for “${payload.session.wake_word || 'Echo'}”.`); if (voiceRuntime.permission === 'granted') scheduleCapture(100); }
    catch (error) { showToast('Voice could not be disabled', error.message, 'alert'); }
  };

  const shutdownVoice = async () => {
    if (!voiceRuntime.session) return;
    voiceRuntime.requestController?.abort?.(); stopSpeech(); stopCapture({release: true});
    try { const payload = await voiceFetch(`${voiceEndpoints.sessions}${voiceRuntime.session.id}/shutdown/`, {method: 'POST', body: '{}'}); applyVoiceSession(payload.session, 'Voice is shut down.'); }
    catch (error) { showToast('Voice could not shut down cleanly', error.message, 'alert'); }
  };

  const openVoice = async () => {
    voiceRuntime.previousFocus = document.activeElement;
    if (voiceConsole) { setHidden(voiceConsole, false); $('.js-voice-toggle', voiceConsole)?.focus(); }
    else if (section !== 'voice') { window.location.href = '/workspace/voice/'; return; }
    await initializeVoice();
  };
  const closeVoice = () => { setHidden(voiceConsole, true); voiceRuntime.previousFocus?.focus?.(); };

  $$('.js-open-voice').forEach((button) => button.addEventListener('click', openVoice));
  $$('.js-close-voice').forEach((button) => button.addEventListener('click', closeVoice));
  $$('.js-voice-toggle').forEach((button) => button.addEventListener('click', activateVoice));
  $$('.js-voice-disable,.js-voice-pause').forEach((button) => button.addEventListener('click', disableVoice));
  $$('.js-voice-shutdown,.js-voice-stop').forEach((button) => button.addEventListener('click', shutdownVoice));
  $$('.js-stop-current-task').forEach((button) => button.addEventListener('click', async () => {
    try {
      if (voiceRuntime.currentOperationId) { await mutateComputerOperation(voiceRuntime.currentOperationId, 'cancel'); return; }
      if (voiceRuntime.currentAgentTaskId) {
        const payload = await voiceFetch(`/api/v1/agent-manager/orchestration/tasks/${voiceRuntime.currentAgentTaskId}/cancel/`, {method: 'POST', body: '{}'});
        showToast('Task cancellation requested', payload.task?.current_operation || 'Echo is stopping the current task safely.', 'check-circle');
        return;
      }
      showToast('No cancellable task', 'Echo has no active task to stop.', 'alert');
    } catch (error) { showToast('Task could not be stopped', error.message, 'alert'); }
  }));

  $$('.js-voice-text-form').forEach((form) => form.addEventListener('submit', async (event) => {
    event.preventDefault(); const input = $('textarea', form); const text = input?.value.trim(); if (!text) return;
    input.disabled = true;
    try { await initializeVoice(); await submitVoiceTranscript(text, {provider: 'typed', confidence: 1}); input.value = ''; autoResize(input); }
    finally { input.disabled = false; }
  }));

  $$('[data-voice-setting]').forEach((control) => control.addEventListener('change', async () => {
    const key = control.dataset.voiceSetting; const value = control.type === 'checkbox' ? control.checked : ['range', 'number'].includes(control.type) ? Number(control.value) : control.value;
    control.disabled = true;
    try { const payload = await voiceFetch(voiceEndpoints.profile, {method: 'PATCH', body: JSON.stringify({[key]: value})}); voiceRuntime.profile = payload.profile; renderVoiceState(); }
    catch (error) { showToast('Setting not updated', error.message, 'alert'); }
    finally { control.disabled = false; }
  }));

  const captureSpeakerEnrollmentSample = async (button) => {
    button.disabled = true; stopCapture({release: true});
    try {
      const stream = await requestMicrophone(); await new Promise((resolve) => setTimeout(resolve, 2800)); const embedding = takeSpeakerFingerprint(); releaseMicrophone();
      if (embedding.length < 8) throw new Error('Not enough clear speech was detected.');
      const payload = await voiceFetch(voiceEndpoints.speakerEnroll, {method: 'POST', body: JSON.stringify({embedding, quality: 1, duration_ms: 2800})}); voiceRuntime.speakerProfile = payload.speaker; showToast('Voice sample added', 'Speaker enrollment updated.', 'check-circle');
    } catch (error) { releaseMicrophone(); showToast('Voice sample not saved', error.message, 'alert'); }
    finally { button.disabled = false; scheduleCapture(120); }
  };
  $$('.js-enroll-speaker').forEach((button) => button.addEventListener('click', () => captureSpeakerEnrollmentSample(button)));
  $$('.js-clear-speaker').forEach((button) => button.addEventListener('click', async () => { try { const payload = await voiceFetch(voiceEndpoints.speaker, {method: 'DELETE', body: '{}'}); voiceRuntime.speakerProfile = payload.speaker; showToast('Speaker enrollment cleared', 'Derived speaker data was removed.', 'check-circle'); } catch (error) { showToast('Speaker data not cleared', error.message, 'alert'); } }));
  $$('.js-clear-voice-data').forEach((button) => button.addEventListener('click', async () => { try { const payload = await voiceFetch(voiceEndpoints.privacy, {method: 'POST', body: JSON.stringify({clear_voice_data: true})}); showToast('Voice history cleared', `Removed ${payload.voice_data?.transcripts || 0} transcripts.`, 'check-circle'); await refreshVoiceRuntime(); } catch (error) { showToast('Voice history not cleared', error.message, 'alert'); } }));
  $$('[data-load-voice-session]').forEach((button) => button.addEventListener('click', async () => { try { const payload = await voiceFetch(`${voiceEndpoints.sessions}${button.dataset.loadVoiceSession}/`); renderVoiceSession(payload.session); } catch (error) { showToast('Session unavailable', error.message, 'alert'); } }));

  document.addEventListener('click', async (event) => {
    const action = event.target.closest('[data-memory-action]'); if (!action) return; const decision = action.closest('[data-memory-decision]'); if (!decision) return;
    try { const approve = action.dataset.memoryAction === 'approve'; await voiceFetch(`/api/v1/voice/transcripts/${decision.dataset.memoryDecision}/memory/`, {method: 'POST', body: JSON.stringify({approve})}); decision.innerHTML = `<span>${approve ? 'Saved to memory' : 'Memory discarded'}</span>`; }
    catch (error) { showToast('Memory decision failed', error.message, 'alert'); }
  });

  voiceConsole?.addEventListener('click', (event) => { if (event.target === voiceConsole) closeVoice(); });
  document.addEventListener('visibilitychange', () => { if (document.hidden) stopCapture({release: true}); else if (voiceCanCapture()) scheduleCapture(120); });
  window.addEventListener('beforeunload', () => { stopCapture({release: true}); stopSpeech(); if (voiceRuntime.clockTimer) clearInterval(voiceRuntime.clockTimer); if (voiceRuntime.runtimePollTimer) clearInterval(voiceRuntime.runtimePollTimer); });
  initializeVoice();

  if (document.querySelector('[data-computer-use-operations]')) pollComputerOperations();


  $('.js-mobile-nav')?.addEventListener('click', () => root.classList.toggle('nav-open'));
  $('.js-collapse-context')?.addEventListener('click', () => root.classList.remove('nav-open'));
  $('.js-toggle-presence')?.addEventListener('click', () => root.classList.toggle('presence-open'));
  $('.js-close-presence')?.addEventListener('click', () => root.classList.remove('presence-open'));
  $('.js-profile-toggle')?.addEventListener('click', (event) => {
    event.stopPropagation();
    profileMenu.hidden = !profileMenu.hidden;
  });
  document.addEventListener('click', (event) => {
    if (profileMenu && !profileMenu.hidden && !event.target.closest('#profile-menu') && !event.target.closest('.js-profile-toggle')) profileMenu.hidden = true;
  });

  $('[data-copy-env]')?.addEventListener('click', async () => {
    const value = 'AI_PROVIDER_BASE_URL=\nAI_PROVIDER_API_KEY=\nAI_PROVIDER_MODEL=';
    try {
      await navigator.clipboard.writeText(value);
      showToast('Configuration keys copied', 'Add the values securely to your .env file.', 'check-circle');
    } catch {
      showToast('Copy unavailable', value, 'alert', 9000);
    }
  });

  [commandPalette, createModal].forEach((modal) => modal?.addEventListener('click', (event) => {
    if (event.target === modal) setHidden(modal, true);
  }));

  document.addEventListener('keydown', (event) => {
    const modifier = event.metaKey || event.ctrlKey;
    if (modifier && event.key.toLowerCase() === 'k') {
      event.preventDefault();
      commandPalette?.hidden ? openPalette() : closePalette();
    }
    if (modifier && event.shiftKey && event.key.toLowerCase() === 'v') {
      event.preventDefault();
      openVoice();
    }
    if (modifier && event.key.toLowerCase() === 'n') {
      event.preventDefault();
      focusComposer();
    }
    if (modifier && event.key === 'Enter') {
      const active = document.activeElement;
      if (active?.matches('.js-command-form textarea,.js-command-form input[name="prompt"]')) active.closest('form')?.requestSubmit();
      else focusComposer();
    }
    if (event.key === 'Escape') {
      closePalette();
      closeCreate();
      if (voiceConsole && !voiceConsole.hidden) closeVoice();
      root.classList.remove('nav-open', 'presence-open');
      if (profileMenu) profileMenu.hidden = true;
    }
  });
})();
