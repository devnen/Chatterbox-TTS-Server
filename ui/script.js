// ui/script.js
// Client-side JavaScript for the Chatterbox TTS Server web interface.
// Handles UI interactions, API communication, audio playback, and settings management.

document.addEventListener('DOMContentLoaded', async function () {
    // --- Global Flags & State ---
    let uiReady = false;
    let listenersAttached = false;
    let isGenerating = false;
    let wavesurfer = null;
    let currentAudioBlobUrl = null;
    let saveStateTimeout = null;
    let currentPresetName = null;

    let currentConfig = {};
    let currentUiState = {};
    let appPresets = [];
    let initialReferenceFiles = [];
    let initialPredefinedVoices = [];

    // Model information state
    let currentModelInfo = null;
    let selectedModelSelector = 'chatterbox-turbo';
    let modelChangesPending = false;

    let hideChunkWarning = false;
    let hideGenerationWarning = false;
    let currentVoiceMode = 'predefined';

    const IS_LOCAL_FILE = window.location.protocol === 'file:';
    // If you always access the server via localhost
    const API_BASE_URL = IS_LOCAL_FILE ? 'http://localhost:8004' : '';

    const DEBOUNCE_DELAY_MS = 750;


    // --- DOM Element Selectors ---
    const appTitleLink = document.getElementById('app-title-link');
    const themeToggleButton = document.getElementById('theme-toggle-btn');
    const themeSwitchThumb = themeToggleButton ? themeToggleButton.querySelector('.theme-switch-thumb') : null;
    const notificationArea = document.getElementById('notification-area');
    const ttsForm = document.getElementById('tts-form');
    const ttsFormHeader = document.getElementById('tts-form-header');
    const textArea = document.getElementById('text');
    const charCount = document.getElementById('char-count');
    const generateBtn = document.getElementById('generate-btn');
    const splitTextToggle = document.getElementById('split-text-toggle');
    const chunkSizeControls = document.getElementById('chunk-size-controls');
    const chunkSizeSlider = document.getElementById('chunk-size-slider');
    const chunkSizeValue = document.getElementById('chunk-size-value');
    const chunkExplanation = document.getElementById('chunk-explanation');
    const voiceModeRadios = document.querySelectorAll('input[name="voice_mode"]');
    const predefinedVoiceOptionsDiv = document.getElementById('predefined-voice-options');
    const predefinedVoiceSelect = document.getElementById('predefined-voice-select');
    const predefinedVoiceImportButton = document.getElementById('predefined-voice-import-button');
    const predefinedVoiceRefreshButton = document.getElementById('predefined-voice-refresh-button');
    const predefinedVoiceFileInput = document.getElementById('predefined-voice-file-input');
    const cloneOptionsDiv = document.getElementById('clone-options');
    const cloneReferenceSelect = document.getElementById('clone-reference-select');
    const cloneImportButton = document.getElementById('clone-import-button');
    const cloneRefreshButton = document.getElementById('clone-refresh-button');
    const cloneFileInput = document.getElementById('clone-file-input');
    const presetsContainer = document.getElementById('presets-container');
    const presetsPlaceholder = document.getElementById('presets-placeholder');
    const temperatureSlider = document.getElementById('temperature');
    const temperatureValueDisplay = document.getElementById('temperature-value');
    const exaggerationSlider = document.getElementById('exaggeration');
    const exaggerationValueDisplay = document.getElementById('exaggeration-value');
    const cfgWeightSlider = document.getElementById('cfg-weight');
    const cfgWeightValueDisplay = document.getElementById('cfg-weight-value');
    const speedFactorSlider = document.getElementById('speed-factor');
    const speedFactorValueDisplay = document.getElementById('speed-factor-value');
    const speedFactorWarningSpan = document.getElementById('speed-factor-warning');
    const seedInput = document.getElementById('seed');
    const languageSelectContainer = document.getElementById('language-select-container');
    const languageSelect = document.getElementById('language');
    const outputFormatSelect = document.getElementById('output-format');
    const saveGenDefaultsBtn = document.getElementById('save-gen-defaults-btn');
    const genDefaultsStatus = document.getElementById('gen-defaults-status');
    const serverConfigForm = document.getElementById('server-config-form');
    const saveConfigBtn = document.getElementById('save-config-btn');
    const restartServerBtn = document.getElementById('restart-server-btn');
    const configStatus = document.getElementById('config-status');
    const resetSettingsBtn = document.getElementById('reset-settings-btn');
    const audioPlayerContainer = document.getElementById('audio-player-container');
    const loadingOverlay = document.getElementById('loading-overlay');
    const loadingMessage = document.getElementById('loading-message');
    const loadingStatusText = document.getElementById('loading-status');
    const loadingCancelBtn = document.getElementById('loading-cancel-btn');
    const chunkWarningModal = document.getElementById('chunk-warning-modal');
    const chunkWarningOkBtn = document.getElementById('chunk-warning-ok');
    const chunkWarningCancelBtn = document.getElementById('chunk-warning-cancel');
    const hideChunkWarningCheckbox = document.getElementById('hide-chunk-warning-checkbox');
    const generationWarningModal = document.getElementById('generation-warning-modal');
    const generationWarningAcknowledgeBtn = document.getElementById('generation-warning-acknowledge');
    const hideGenerationWarningCheckbox = document.getElementById('hide-generation-warning-checkbox');

    // Model-related elements
    const modelIndicator = document.getElementById('model-indicator');
    const modelBadge = document.getElementById('model-badge');
    const modelBadgeIcon = document.getElementById('model-badge-icon');
    const modelBadgeText = document.getElementById('model-badge-text');
    const modelSelect = document.getElementById('model-select');
    const modelStatusIndicator = document.getElementById('model-status-indicator');
    const modelStatusText = document.getElementById('model-status-text');
    const applyModelBtn = document.getElementById('apply-model-btn');
    const paralinguisticTagsSection = document.getElementById('paralinguistic-tags-section');
    const tagButtons = document.querySelectorAll('.tag-btn');


    // Handle voice mode selection visual feedback
    const voiceModeOptions = document.querySelectorAll('.voice-mode__option');

    voiceModeRadios.forEach(radio => {
        radio.addEventListener('change', function () {
            // Remove selected class from all options
            voiceModeOptions.forEach(option => {
                option.classList.remove('selected');
            });

            // Add selected class to the parent of the checked radio
            // CORRECTED: Selector updated to match HTML
            const selectedOption = this.closest('.voice-mode__option');
            if (selectedOption) {
                selectedOption.classList.add('selected');
            }
        });
    });

    // Set initial state
    const checkedRadio = document.querySelector('input[name="voice_mode"]:checked');
    if (checkedRadio) {
        // CORRECTED: Selector updated to match HTML
        const selectedOption = checkedRadio.closest('.voice-mode__option');
        if (selectedOption) {
            selectedOption.classList.add('selected');
        }
    }

    // --- Utility Functions ---
    function showNotification(message, type = 'info', duration = 5000) {
        if (!notificationArea) return null;

        const icons = {
            success: '<svg class="notification__icon" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd" /></svg>',
            error: '<svg class="notification__icon" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd" /></svg>',
            warning: '<svg class="notification__icon" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M8.485 2.495c.673-1.167 2.357-1.167 3.03 0l6.28 10.875c.673 1.167-.17 2.625-1.516 2.625H3.72c-1.347 0-2.189-1.458-1.515-2.625L8.485 2.495zM10 5a.75.75 0 01.75.75v3.5a.75.75 0 01-1.5 0v-3.5A.75.75 0 0110 5zm0 9a1 1 0 100-2 1 1 0 000 2z" clip-rule="evenodd" /></svg>',
            info: '<svg class="notification__icon" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a.75.75 0 000 1.5h.253a.25.25 0 01.244.304l-.459 2.066A1.75 1.75 0 0010.747 15H11a.75.75 0 000-1.5h-.253a.25.25 0 01-.244-.304l.459-2.066A1.75 1.75 0 009.253 9H9z" clip-rule="evenodd" /></svg>'
        };

        const notificationDiv = document.createElement('div');
        notificationDiv.className = `notification ${type}`;
        notificationDiv.setAttribute('role', 'alert');

        // Build notification structure
        notificationDiv.innerHTML = `
            ${icons[type] || icons['info']}
            <div class="notification__content"><span>${message}</span></div>
        `;

        // Create close button
        const closeButton = document.createElement('button');
        closeButton.type = 'button';
        closeButton.className = 'notification__close';
        closeButton.innerHTML = `
            <span class="sr-only">Close</span>
            <svg class="notification__close-icon" fill="currentColor" viewBox="0 0 20 20">
                <path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd"></path>
            </svg>
        `;
        closeButton.onclick = () => {
            notificationDiv.style.transition = 'opacity 0.3s ease, transform 0.3s ease';
            notificationDiv.style.opacity = '0';
            notificationDiv.style.transform = 'translateY(-20px)';
            setTimeout(() => notificationDiv.remove(), 300);
        };

        notificationDiv.appendChild(closeButton);
        notificationArea.appendChild(notificationDiv);

        if (duration > 0) {
            setTimeout(() => closeButton.click(), duration);
        }

        return notificationDiv;
    }

    function formatTime(seconds) {
        const minutes = Math.floor(seconds / 60);
        const secs = Math.floor(seconds % 60).toString().padStart(2, '0');
        return `${minutes}:${secs}`;
    }

    // --- Theme Management ---
    function applyTheme(theme) {
        const isDark = theme === 'dark';
        document.documentElement.classList.toggle('dark', isDark);

        // WaveSurfer color update
        if (wavesurfer) {
            wavesurfer.setOptions({
                waveColor: isDark ? '#6366f1' : '#a5b4fc',
                progressColor: isDark ? '#4f46e5' : '#6366f1',
                cursorColor: isDark ? '#cbd5e1' : '#475569',
            });
        }

        localStorage.setItem('uiTheme', theme);
    }

    if (themeToggleButton) {
        themeToggleButton.addEventListener('click', () => {
            const newTheme = document.documentElement.classList.contains('dark') ? 'light' : 'dark';
            applyTheme(newTheme);
            debouncedSaveState();
        });
    }

    // --- UI State Persistence ---
    async function saveCurrentUiState() {
        const stateToSave = {
            last_text: textArea ? textArea.value : '',
            last_voice_mode: currentVoiceMode,
            last_predefined_voice: predefinedVoiceSelect ? predefinedVoiceSelect.value : null,
            last_reference_file: cloneReferenceSelect ? cloneReferenceSelect.value : null,
            last_seed: seedInput ? parseInt(seedInput.value, 10) || 0 : 0,
            last_chunk_size: chunkSizeSlider ? parseInt(chunkSizeSlider.value, 10) : 120,
            last_split_text_enabled: splitTextToggle ? splitTextToggle.checked : true,
            hide_chunk_warning: hideChunkWarning,
            hide_generation_warning: hideGenerationWarning,
            theme: localStorage.getItem('uiTheme') || 'dark',
            last_preset_name: currentPresetName,
        };

        try {
            const response = await fetch(`${API_BASE_URL}/save_settings`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ ui_state: stateToSave })
            });
            if (!response.ok) {
                const errorResult = await response.json();
                throw new Error(errorResult.detail || `Failed to save UI state (status ${response.status})`);
            }
        } catch (error) {
            console.error("Error saving UI state via API:", error);
            showNotification(`Error saving settings: ${error.message}. Some changes may not persist.`, 'error', 0);
        }
    }

    function debouncedSaveState() {
        // Do not save anything until the entire UI has finished its initial setup.
        if (!uiReady || !listenersAttached) { return; }
        clearTimeout(saveStateTimeout);
        saveStateTimeout = setTimeout(saveCurrentUiState, DEBOUNCE_DELAY_MS);
    }

    // --- Speed Factor Warning ---
    function updateSpeedFactorWarning() {
        if (speedFactorSlider && speedFactorWarningSpan) {
            const value = parseFloat(speedFactorSlider.value);
            if (value !== 1.0) {
                speedFactorWarningSpan.textContent = "* Experimental, may cause echo.";
                speedFactorWarningSpan.classList.remove('hidden');
            } else {
                speedFactorWarningSpan.classList.add('hidden');
            }
        }
    }

    // --- Model Management Functions (New Features) ---

    function updateModelUI(modelInfo) {
        if (!modelInfo) {
            console.warn('updateModelUI called with null modelInfo');
            return;
        }

        currentModelInfo = modelInfo;

        // Update model indicator badge
        if (modelIndicator && modelBadge) {
            modelIndicator.classList.remove('hidden');

            // Use simplified modifier classes
            modelBadge.className = modelInfo.type === 'turbo'
                ? 'model-badge turbo'
                : 'model-badge original';
            modelBadgeText.textContent = modelInfo.type === 'turbo' ? '⚡ Turbo' : 'Original';
        }

        // Update model status indicator
        if (modelStatusIndicator && modelStatusText) {
            if (modelInfo.loaded) {
                modelStatusIndicator.className = 'status-dot success';
                modelStatusText.textContent = `${modelInfo.class_name} loaded on ${modelInfo.device}`;
                modelStatusText.className = 'model-status__text success';
            } else {
                modelStatusIndicator.className = 'status-dot error';
                modelStatusText.textContent = 'Model not loaded';
                modelStatusText.className = 'model-status__text error';
            }
        }

        // Update model selector dropdown to match loaded model
        if (modelSelect && !modelChangesPending) {
            const selectorValue = modelInfo.type === 'turbo' ? 'chatterbox-turbo' : 'chatterbox';
            modelSelect.value = selectorValue;
            selectedModelSelector = selectorValue;
        }

        // Show/hide model-specific UI sections
        const exaggerationGroup = document.getElementById('exaggeration-group');
        const cfgWeightGroup = document.getElementById('cfg-weight-group');

        // Show/hide paralinguistic tags section (Turbo only)
        if (paralinguisticTagsSection) {
            if (modelInfo.type === 'turbo' && modelInfo.supports_paralinguistic_tags) {
                paralinguisticTagsSection.classList.remove('hidden');
            } else {
                paralinguisticTagsSection.classList.add('hidden');
            }
        }

        // Hide exaggeration and CFG for turbo model
        if (modelInfo.type === 'turbo') {
            exaggerationGroup?.classList.add('hidden');
            cfgWeightGroup?.classList.add('hidden');
        } else {
            exaggerationGroup?.classList.remove('hidden');
            cfgWeightGroup?.classList.remove('hidden');
        }

        // Refresh presets to filter based on current model type
        populatePresets();

        console.log('Model UI updated:', modelInfo);
    }

    function insertTagAtCursor(tag) {
        if (!textArea) return;

        const startPos = textArea.selectionStart;
        const endPos = textArea.selectionEnd;
        const textBefore = textArea.value.substring(0, startPos);
        const textAfter = textArea.value.substring(endPos);

        // Insert tag with a space after if not at end and next char isn't a space
        let insertText = tag;
        if (textAfter.length > 0 && textAfter[0] !== ' ') {
            insertText = tag + ' ';
        }

        textArea.value = textBefore + insertText + textAfter;

        // Update cursor position to after the inserted tag
        const newCursorPos = startPos + insertText.length;
        textArea.setSelectionRange(newCursorPos, newCursorPos);
        textArea.focus();

        // Update character count
        if (charCount) {
            charCount.textContent = textArea.value.length;
        }

        // Trigger state save
        debouncedSaveState();
    }

    function handleModelSelectChange() {
        if (!modelSelect) return;

        const newSelector = modelSelect.value;
        const currentSelector = currentModelInfo?.type === 'turbo' ? 'chatterbox-turbo' : 'chatterbox';

        if (newSelector !== currentSelector) {
            modelChangesPending = true;

            // Show the apply button
            if (applyModelBtn) {
                applyModelBtn.classList.remove('hidden');
            }

            // Update status indicator and text to show pending state
            if (modelStatusIndicator) {
                modelStatusIndicator.className = 'status-dot warning';
            }
            if (modelStatusText) {
                modelStatusText.textContent = 'Model change pending - click Apply & Restart';
                modelStatusText.className = 'model-status__text warning';
            }
        } else {
            modelChangesPending = false;

            // Hide the apply button
            if (applyModelBtn) {
                applyModelBtn.classList.add('hidden');
            }

            // Restore status from current model info
            updateModelUI(currentModelInfo);
        }
    }


    async function applyModelChange() {
        if (!modelSelect) return;

        const newSelector = modelSelect.value;

        // Update status
        if (modelStatusText) {
            modelStatusText.textContent = 'Saving configuration...';
        }
        if (applyModelBtn) {
            applyModelBtn.disabled = true;
            applyModelBtn.innerHTML = `
                <svg class="btn__icon animate-spin" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                    <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                    <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                Saving...
            `;
        }

        try {
            // Save the model selector to config
            const response = await fetch(`${API_BASE_URL}/save_settings`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    model: {
                        repo_id: newSelector
                    }
                })
            });

            if (!response.ok) {
                const errorResult = await response.json().catch(() => ({ detail: 'Failed to save' }));
                throw new Error(errorResult.detail || 'Failed to save model configuration');
            }

            showNotification('Model configuration saved. Initiating server restart...', 'info');

            // Trigger server restart
            const restartResponse = await fetch(`${API_BASE_URL}/restart_server`, {
                method: 'POST'
            });

            if (restartResponse.ok) {
                showNotification(
                    'Server restart initiated. The page will reload automatically in a few seconds...',
                    'success',
                    10000
                );

                // Attempt to reload after delay
                setTimeout(() => {
                    window.location.reload();
                }, 5000);
            } else {
                showNotification(
                    'Configuration saved. Please restart the server manually for changes to take effect.',
                    'warning',
                    0
                );
            }

        } catch (error) {
            console.error('Error applying model change:', error);
            showNotification(`Error: ${error.message}`, 'error');

            // Re-enable button
            if (applyModelBtn) {
                applyModelBtn.disabled = false;
                applyModelBtn.innerHTML = `
                    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-4 h-4 mr-1">
                        <path stroke-linecap="round" stroke-linejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0 3.181 3.183a8.25 8.25 0 0 0 13.803-3.7M4.031 9.865a8.25 8.25 0 0 1 13.803-3.7l3.181 3.182m0-4.991v4.99" />
                    </svg>
                    Apply & Restart
                `;
            }
        }
    }


    // --- Initial Application Setup ---
    function initializeApplication() {
        const preferredTheme = localStorage.getItem('uiTheme') || currentUiState.theme || 'dark';
        applyTheme(preferredTheme);
        const pageTitle = currentConfig?.ui?.title || "Chatterbox TTS Server";
        document.title = pageTitle;
        if (appTitleLink) appTitleLink.textContent = pageTitle;
        if (ttsFormHeader) ttsFormHeader.textContent = `Generate Speech`;
        loadInitialUiState();
        populatePredefinedVoices();
        populateReferenceFiles();
        populatePresets();
        displayServerConfiguration();
        if (languageSelectContainer && currentConfig?.ui?.show_language_select === false) {
            languageSelectContainer.classList.add('hidden');
        }
        updateSpeedFactorWarning(); // Initial check for speed factor warning
        const initialGenResult = currentConfig.initial_gen_result;
        if (initialGenResult && initialGenResult.outputUrl) {
            initializeWaveSurfer(initialGenResult.outputUrl, initialGenResult);
        }
    }

    async function fetchInitialData() {
        try {
            const response = await fetch(`${API_BASE_URL}/api/ui/initial-data`);
            if (!response.ok) {
                const errorText = await response.text();
                throw new Error(`Failed to fetch initial UI data: ${response.status} ${response.statusText}. Server response: ${errorText}`);
            }
            const data = await response.json();
            currentConfig = data.config || {};
            currentUiState = currentConfig.ui_state || {};
            appPresets = data.presets || [];
            initialReferenceFiles = data.reference_files || [];
            initialPredefinedVoices = data.predefined_voices || [];
            hideChunkWarning = currentUiState.hide_chunk_warning || false;
            hideGenerationWarning = currentUiState.hide_generation_warning || false;
            currentVoiceMode = currentUiState.last_voice_mode || 'predefined';

            // NEW: Handle model info from initial data
            if (data.model_info) {
                updateModelUI(data.model_info);
            }

            initializeApplication();

        } catch (error) {
            console.error("Error fetching initial data:", error);
            showNotification(`Could not load essential application data: ${error.message}. Please try refreshing.`, 'error', 0);
            if (Object.keys(currentConfig).length === 0) {
                currentConfig = { ui: { title: "Chatterbox TTS Server (Error Mode)" }, generation_defaults: {}, ui_state: {} };
                currentUiState = currentConfig.ui_state;
            }
            initializeApplication(); // Attempt to init in a degraded state
        } finally {
            // --- PHASE 2: Attach listeners and enable UI readiness ---
            // This pushes the listener attachment to the end of the event queue,
            // ensuring all initialization events have fired harmlessly before we start listening.
            setTimeout(() => {
                attachStateSavingListeners();
                listenersAttached = true;
                uiReady = true;
            }, 50); // A 50ms delay is more robust than 0ms for complex UIs.
        }
    }

    function loadInitialUiState() {
        if (textArea && currentUiState.last_text) {
            textArea.value = currentUiState.last_text;
            if (charCount) charCount.textContent = textArea.value.length;
        }

        // Handle Voice Mode Selection
        const modeRadioToSelect = document.querySelector(`input[name="voice_mode"][value="${currentVoiceMode}"]`);

        if (modeRadioToSelect) {
            modeRadioToSelect.checked = true;
            // FIX: Manually fire the change event so the .selected class updates visually
            modeRadioToSelect.dispatchEvent(new Event('change'));
        } else {
            const defaultRadio = document.querySelector('input[name="voice_mode"][value="predefined"]');
            if (defaultRadio) {
                defaultRadio.checked = true;
                currentVoiceMode = 'predefined';
                defaultRadio.dispatchEvent(new Event('change'));
            }
        }

        toggleVoiceOptionsDisplay();

        if (seedInput && currentUiState.last_seed !== undefined) seedInput.value = currentUiState.last_seed;
        else if (seedInput && currentConfig?.generation_defaults?.seed !== undefined) seedInput.value = currentConfig.generation_defaults.seed;

        if (splitTextToggle) splitTextToggle.checked = currentUiState.last_split_text_enabled !== undefined ? currentUiState.last_split_text_enabled : true;

        if (chunkSizeSlider && currentUiState.last_chunk_size !== undefined) chunkSizeSlider.value = currentUiState.last_chunk_size;
        if (chunkSizeValue) chunkSizeValue.textContent = chunkSizeSlider ? chunkSizeSlider.value : '120';
        toggleChunkControlsVisibility();

        const genDefaults = currentConfig.generation_defaults || {};
        if (temperatureSlider) temperatureSlider.value = genDefaults.temperature !== undefined ? genDefaults.temperature : 0.8;
        if (temperatureValueDisplay) temperatureValueDisplay.textContent = temperatureSlider.value;
        if (exaggerationSlider) exaggerationSlider.value = genDefaults.exaggeration !== undefined ? genDefaults.exaggeration : 0.5;
        if (exaggerationValueDisplay) exaggerationValueDisplay.textContent = exaggerationSlider.value;
        if (cfgWeightSlider) cfgWeightSlider.value = genDefaults.cfg_weight !== undefined ? genDefaults.cfg_weight : 0.5;
        if (cfgWeightValueDisplay) cfgWeightValueDisplay.textContent = cfgWeightSlider.value;
        if (speedFactorSlider) speedFactorSlider.value = genDefaults.speed_factor !== undefined ? genDefaults.speed_factor : 1.0;
        if (speedFactorValueDisplay) speedFactorValueDisplay.textContent = speedFactorSlider.value;
        if (languageSelect) languageSelect.value = genDefaults.language || 'en';
        if (outputFormatSelect) outputFormatSelect.value = currentConfig?.audio_output?.format || 'mp3';

        if (hideChunkWarningCheckbox) hideChunkWarningCheckbox.checked = hideChunkWarning;
        if (hideGenerationWarningCheckbox) hideGenerationWarningCheckbox.checked = hideGenerationWarning;

        // --- PRESET RESTORATION LOGIC ---

        // 1. Restore the name from state variable
        if (currentUiState.last_preset_name) {
            currentPresetName = currentUiState.last_preset_name;
        }

        // 2. Logic to apply preset (if empty) OR just highlight button (if text exists)
        if (textArea && !textArea.value && appPresets && appPresets.length > 0) {
            // Case A: No text entered. We want to load a preset fully.
            // Priority: Saved preset > "Standard Narration" > First available
            const savedPreset = appPresets.find(p => p.name === currentPresetName);
            const defaultPreset = savedPreset || appPresets.find(p => p.name === "Standard Narration") || appPresets[0];

            if (defaultPreset) {
                // Apply values AND visuals, no notification, no save
                applyPreset(defaultPreset, false, false);
            }
        } else if (currentPresetName) {
            // Case B: Text already exists (restored from last_text). 
            // We don't want to overwrite parameters, but we want to show which preset button was active.
            updatePresetVisuals(currentPresetName);
        }
    }

    function attachStateSavingListeners() {
        voiceModeRadios.forEach(radio => {
            radio.addEventListener('change', debouncedSaveState);
        });

        if (textArea) textArea.addEventListener('input', () => { if (charCount) charCount.textContent = textArea.value.length; debouncedSaveState(); });
        if (predefinedVoiceSelect) predefinedVoiceSelect.addEventListener('change', debouncedSaveState);
        if (cloneReferenceSelect) cloneReferenceSelect.addEventListener('change', debouncedSaveState);
        if (seedInput) seedInput.addEventListener('change', debouncedSaveState);
        if (splitTextToggle) splitTextToggle.addEventListener('change', () => { toggleChunkControlsVisibility(); debouncedSaveState(); });
        if (chunkSizeSlider) {
            chunkSizeSlider.addEventListener('input', () => { if (chunkSizeValue) chunkSizeValue.textContent = chunkSizeSlider.value; });
            chunkSizeSlider.addEventListener('change', debouncedSaveState);
        }
        const genParamSliders = [temperatureSlider, exaggerationSlider, cfgWeightSlider, speedFactorSlider];
        genParamSliders.forEach(slider => {
            if (slider) {
                const valueDisplayId = slider.id + '-value';
                const valueDisplay = document.getElementById(valueDisplayId);
                slider.addEventListener('input', () => {
                    if (valueDisplay) valueDisplay.textContent = slider.value;
                    if (slider.id === 'speed-factor') updateSpeedFactorWarning(); // Update warning on input
                });
                slider.addEventListener('change', debouncedSaveState);
            }
        });
        if (languageSelect) languageSelect.addEventListener('change', debouncedSaveState);
        if (outputFormatSelect) outputFormatSelect.addEventListener('change', debouncedSaveState);

        // NEW: Model management listeners
        if (modelSelect) {
            modelSelect.addEventListener('change', handleModelSelectChange);
        }

        if (applyModelBtn) {
            applyModelBtn.addEventListener('click', applyModelChange);
        }

        // NEW: Tag button listeners
        tagButtons.forEach(button => {
            button.addEventListener('click', (e) => {
                const tag = e.currentTarget.getAttribute('data-tag');
                if (tag) {
                    insertTagAtCursor(tag);
                }
            });
        });
    }

    // --- Dynamic UI Population ---
    function populatePredefinedVoices(voicesData = initialPredefinedVoices) {
        if (!predefinedVoiceSelect) return;
        const currentSelectedValue = predefinedVoiceSelect.value;
        predefinedVoiceSelect.innerHTML = '<option value="none">-- Select Voice --</option>';
        voicesData.forEach(voice => {
            const option = document.createElement('option');
            option.value = voice.filename;
            option.textContent = voice.display_name || voice.filename;
            predefinedVoiceSelect.appendChild(option);
        });
        const lastSelected = currentUiState.last_predefined_voice;
        const defaultFromConfig = currentConfig?.tts_engine?.default_voice_id;
        if (currentSelectedValue !== 'none' && voicesData.some(v => v.filename === currentSelectedValue)) {
            predefinedVoiceSelect.value = currentSelectedValue;
        } else if (lastSelected && voicesData.some(v => v.filename === lastSelected)) {
            predefinedVoiceSelect.value = lastSelected;
        } else if (defaultFromConfig && voicesData.some(v => v.filename === defaultFromConfig)) {
            predefinedVoiceSelect.value = defaultFromConfig;
        } else {
            predefinedVoiceSelect.value = 'none';
        }
    }

    function populateReferenceFiles(filesData = initialReferenceFiles) {
        if (!cloneReferenceSelect) return;
        const currentSelectedValue = cloneReferenceSelect.value;
        cloneReferenceSelect.innerHTML = '<option value="none">-- Select Reference File --</option>';
        filesData.forEach(filename => {
            const option = document.createElement('option');
            option.value = filename;
            option.textContent = filename;
            cloneReferenceSelect.appendChild(option);
        });
        const lastSelected = currentUiState.last_reference_file;
        if (currentSelectedValue !== 'none' && filesData.includes(currentSelectedValue)) {
            cloneReferenceSelect.value = currentSelectedValue;
        } else if (lastSelected && filesData.includes(lastSelected)) {
            cloneReferenceSelect.value = lastSelected;
        } else {
            cloneReferenceSelect.value = 'none';
        }
    }

    function updatePresetVisuals(name) {
        currentPresetName = name;

        // Find all preset buttons
        const buttons = document.querySelectorAll('.preset-btn');
        buttons.forEach(btn => {
            // We will add data-name to buttons in the next step
            if (btn.dataset.name === name) {
                btn.classList.add('selected');
            } else {
                btn.classList.remove('selected');
            }
        });
    }

    function populatePresets() {
        if (!presetsContainer || !appPresets) return;

        // Filter presets based on current model
        // Hide "Turbo" presets when Chatterbox-Original is loaded
        let filteredPresets = appPresets;
        if (currentModelInfo && currentModelInfo.type !== 'turbo') {
            filteredPresets = appPresets.filter(preset =>
                !preset.name.toLowerCase().startsWith('turbo')
            );
        }

        // Clear container
        presetsContainer.innerHTML = '';

        if (filteredPresets.length === 0) {
            const placeholder = document.createElement('p');
            placeholder.className = 'form-hint';
            placeholder.textContent = 'No presets available for this model.';
            presetsContainer.appendChild(placeholder);
            return;
        }

        filteredPresets.forEach((preset, index) => {
            const button = document.createElement('button');
            button.type = 'button';
            button.id = `preset-btn-${index}`;
            button.className = 'preset-btn';
            button.dataset.name = preset.name;
            button.title = `Load '${preset.name}' preset`;
            button.textContent = preset.name;
            button.addEventListener('click', () => applyPreset(preset));
            presetsContainer.appendChild(button);
        });

        if (currentPresetName) {
            updatePresetVisuals(currentPresetName);
        }
    }

    function applyPreset(presetData, showNotif = true, isUserInteraction = true) {
        if (!presetData) return;
        if (textArea && presetData.text !== undefined) {
            textArea.value = presetData.text;
            if (charCount) charCount.textContent = textArea.value.length;
        }
        const genParams = presetData.params || presetData;
        if (temperatureSlider && genParams.temperature !== undefined) temperatureSlider.value = genParams.temperature;
        if (exaggerationSlider && genParams.exaggeration !== undefined) exaggerationSlider.value = genParams.exaggeration;
        if (cfgWeightSlider && genParams.cfg_weight !== undefined) cfgWeightSlider.value = genParams.cfg_weight;
        if (speedFactorSlider && genParams.speed_factor !== undefined) speedFactorSlider.value = genParams.speed_factor;
        if (seedInput && genParams.seed !== undefined) seedInput.value = genParams.seed;
        if (languageSelect && genParams.language !== undefined) languageSelect.value = genParams.language;
        if (temperatureValueDisplay && temperatureSlider) temperatureValueDisplay.textContent = temperatureSlider.value;
        if (exaggerationValueDisplay && exaggerationSlider) exaggerationValueDisplay.textContent = exaggerationSlider.value;
        if (cfgWeightValueDisplay && cfgWeightSlider) cfgWeightValueDisplay.textContent = cfgWeightSlider.value;
        if (speedFactorValueDisplay && speedFactorSlider) speedFactorValueDisplay.textContent = speedFactorSlider.value;
        updateSpeedFactorWarning();

        if (genParams.voice_id && predefinedVoiceSelect) {
            const voiceExists = Array.from(predefinedVoiceSelect.options).some(opt => opt.value === genParams.voice_id);
            if (voiceExists) {
                predefinedVoiceSelect.value = genParams.voice_id;
                const predefinedRadio = document.querySelector('input[name="voice_mode"][value="predefined"]');
                if (predefinedRadio) {
                    predefinedRadio.checked = true;
                    predefinedRadio.dispatchEvent(new Event('change', { bubbles: true }));
                }
                toggleVoiceOptionsDisplay();
            }
        } else if (genParams.reference_audio_filename && cloneReferenceSelect) {
            const refExists = Array.from(cloneReferenceSelect.options).some(opt => opt.value === genParams.reference_audio_filename);
            if (refExists) {
                cloneReferenceSelect.value = genParams.reference_audio_filename;
                const cloneRadio = document.querySelector('input[name="voice_mode"][value="clone"]');
                if (cloneRadio) {
                    cloneRadio.checked = true;
                    cloneRadio.dispatchEvent(new Event('change', { bubbles: true }));
                }
                toggleVoiceOptionsDisplay();
            }
        }

        if (presetData.name) {
            updatePresetVisuals(presetData.name);
        }

        if (showNotif) showNotification(`Preset "${presetData.name}" loaded.`, 'info', 3000);
        if (isUserInteraction) {
            debouncedSaveState();
        }
    }

    // --- Voice Mode and Options Visibility ---
    function toggleVoiceOptionsDisplay() {
        const selectedMode = document.querySelector('input[name="voice_mode"]:checked')?.value;
        currentVoiceMode = selectedMode;
        if (predefinedVoiceOptionsDiv) predefinedVoiceOptionsDiv.classList.toggle('hidden', selectedMode !== 'predefined');
        if (cloneOptionsDiv) cloneOptionsDiv.classList.toggle('hidden', selectedMode !== 'clone');
        if (predefinedVoiceSelect) predefinedVoiceSelect.required = (selectedMode === 'predefined');
        if (cloneReferenceSelect) cloneReferenceSelect.required = (selectedMode === 'clone');
    }
    voiceModeRadios.forEach(radio => radio.addEventListener('change', toggleVoiceOptionsDisplay));

    function toggleChunkControlsVisibility() {
        const isChecked = splitTextToggle ? splitTextToggle.checked : false;
        if (chunkSizeControls) chunkSizeControls.classList.toggle('hidden', !isChecked);
        if (chunkExplanation) chunkExplanation.classList.toggle('hidden', !isChecked);
    }
    if (splitTextToggle) toggleChunkControlsVisibility();

    // --- Audio Player (WaveSurfer) ---
    function initializeWaveSurfer(audioUrl, resultDetails = {}) {
        if (wavesurfer) {
            wavesurfer.unAll(); // Remove all event listeners before destroying
            wavesurfer.destroy();
            wavesurfer = null;
        }
        if (currentAudioBlobUrl) {
            URL.revokeObjectURL(currentAudioBlobUrl);
            currentAudioBlobUrl = null;
        }
        currentAudioBlobUrl = audioUrl;

        // Ensure the container is clean or re-created
        audioPlayerContainer.innerHTML = `
            <div class="card audio-player">
                <div class="card__body">
                    <h2 class="card__title">Generated Audio</h2>
                    <div class="audio-player__waveform" id="waveform"></div>
                    <div class="audio-player__controls">
                        <div class="audio-player__buttons">
                            <button id="play-btn" class="btn primary" disabled>
                                <svg class="btn__icon" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
                                    <path fill-rule="evenodd" d="M2 10a8 8 0 1 1 16 0 8 8 0 0 1-16 0Zm6.39-2.908a.75.75 0 0 1 .766.027l3.5 2.25a.75.75 0 0 1 0 1.262l-3.5 2.25A.75.75 0 0 1 8 12.25v-4.5a.75.75 0 0 1 .39-.658Z" clip-rule="evenodd" />
                                </svg>
                                <span>Play</span>
                            </button>
                            <a id="download-link" href="#" download="tts_output.wav" class="btn secondary disabled">
                                <svg class="btn__icon" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
                                    <path d="M10.75 2.75a.75.75 0 00-1.5 0v8.614L6.295 8.235a.75.75 0 10-1.09 1.03l4.25 4.5a.75.75 0 001.09 0l4.25-4.5a.75.75 0 00-1.09-1.03l-2.955 3.129V2.75z"/>
                                    <path d="M3.5 12.75a.75.75 0 00-1.5 0v2.5A2.75 2.75 0 004.75 18h10.5A2.75 2.75 0 0018 15.25v-2.5a.75.75 0 00-1.5 0v2.5c0 .69-.56 1.25-1.25 1.25H4.75c-.69 0-1.25-.56-1.25-1.25v-2.5z"/>
                                </svg>
                                <span>Download</span>
                            </a>
                        </div>
                        <div class="audio-player__info">
                            Mode: <span id="player-voice-mode" class="text-primary">--</span>
                            <span id="player-voice-file-details"></span>
                            <span class="separator">•</span> Gen Time: <span id="player-gen-time" class="tabular-nums">--s</span>
                            <span class="separator">•</span> Duration: <span id="audio-duration" class="tabular-nums">--:--</span>
                        </div>
                    </div>
                </div>
            </div>`;

        // Re-select elements after recreating them
        const waveformDiv = audioPlayerContainer.querySelector('#waveform');
        const playBtn = audioPlayerContainer.querySelector('#play-btn');
        const downloadLink = audioPlayerContainer.querySelector('#download-link');
        const playerModeSpan = audioPlayerContainer.querySelector('#player-voice-mode');
        const playerFileSpan = audioPlayerContainer.querySelector('#player-voice-file-details');
        const playerGenTimeSpan = audioPlayerContainer.querySelector('#player-gen-time');
        const audioDurationSpan = audioPlayerContainer.querySelector('#audio-duration');

        const audioFilename = resultDetails.filename || (typeof audioUrl === 'string' ? audioUrl.split('/').pop() : 'tts_output.wav');
        if (downloadLink) {
            downloadLink.href = audioUrl;
            downloadLink.download = audioFilename;
            const downloadTextSpan = downloadLink.querySelector('span'); // Target the span for text update
            if (downloadTextSpan) {
                downloadTextSpan.textContent = `Download ${audioFilename.split('.').pop().toUpperCase()}`;
            }
        }
        if (playerModeSpan) playerModeSpan.textContent = resultDetails.submittedVoiceMode || currentVoiceMode || '--';
        if (playerFileSpan) {
            let fileDetail = '';
            if ((resultDetails.submittedVoiceMode || currentVoiceMode) === 'clone' && resultDetails.submittedCloneFile) {
                fileDetail = `(<span class="font-medium text-slate-700 dark:text-slate-300">${resultDetails.submittedCloneFile}</span>)`;
            } else if ((resultDetails.submittedVoiceMode || currentVoiceMode) === 'predefined' && resultDetails.submittedPredefinedVoice) {
                fileDetail = `(<span class="font-medium text-slate-700 dark:text-slate-300">${resultDetails.submittedPredefinedVoice}</span>)`;
            }
            playerFileSpan.innerHTML = fileDetail;
        }
        if (playerGenTimeSpan) playerGenTimeSpan.textContent = resultDetails.genTime ? `${resultDetails.genTime}s` : '--s';

        const playIconSVG = `<svg class="btn__icon" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M2 10a8 8 0 1 1 16 0 8 8 0 0 1-16 0Zm6.39-2.908a.75.75 0 0 1 .766.027l3.5 2.25a.75.75 0 0 1 0 1.262l-3.5 2.25A.75.75 0 0 1 8 12.25v-4.5a.75.75 0 0 1 .39-.658Z" clip-rule="evenodd" /></svg><span>Play</span>`;
        const pauseIconSVG = `<svg class="btn__icon" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M2 10a8 8 0 1 1 16 0 8 8 0 0 1-16 0Zm5-2.25A.75.75 0 0 1 7.75 7h.5a.75.75 0 0 1 .75.75v4.5a.75.75 0 0 1-.75.75h-.5a.75.75 0 0 1-.75-.75v-4.5Zm4 0a.75.75 0 0 1 .75-.75h.5a.75.75 0 0 1 .75.75v4.5a.75.75 0 0 1-.75.75h-.5a.75.75 0 0 1-.75-.75v-4.5Z" clip-rule="evenodd" /></svg><span>Pause</span>`;
        const isDark = document.documentElement.classList.contains('dark');

        wavesurfer = WaveSurfer.create({
            container: waveformDiv, waveColor: isDark ? '#6366f1' : '#a5b4fc', progressColor: isDark ? '#4f46e5' : '#6366f1',
            cursorColor: isDark ? '#cbd5e1' : '#475569', barWidth: 3, barRadius: 3, cursorWidth: 1, height: 80, barGap: 2,
            responsive: true, url: audioUrl, mediaControls: false, normalize: true,
        });

        wavesurfer.on('ready', () => {
            const duration = wavesurfer.getDuration();
            if (audioDurationSpan) audioDurationSpan.textContent = formatTime(duration);
            if (playBtn) {
                playBtn.disabled = false;
                playBtn.innerHTML = playIconSVG;
            }
            if (downloadLink) {
                downloadLink.classList.remove('disabled');
                downloadLink.removeAttribute('aria-disabled');
            }
        });
        wavesurfer.on('play', () => { if (playBtn) playBtn.innerHTML = pauseIconSVG; });
        wavesurfer.on('pause', () => { if (playBtn) playBtn.innerHTML = playIconSVG; });
        wavesurfer.on('finish', () => { if (playBtn) playBtn.innerHTML = playIconSVG; wavesurfer.seekTo(0); });
        wavesurfer.on('error', (err) => {
            console.error("WaveSurfer error:", err);
            showNotification(`Error loading audio waveform: ${err.message || err}`, 'error');
            if (waveformDiv) waveformDiv.innerHTML = `<p class="p-4 text-sm text-red-600 dark:text-red-400">Could not load waveform.</p>`;
            if (playBtn) playBtn.disabled = true;
        });

        if (playBtn) {
            playBtn.onclick = () => {
                if (wavesurfer) {
                    wavesurfer.playPause();
                }
            };
        }
        setTimeout(() => audioPlayerContainer.scrollIntoView({ behavior: 'smooth', block: 'nearest' }), 150);
    }

    // --- TTS Generation Logic ---
    function getTTSFormData() {
        const jsonData = {
            text: textArea.value,
            temperature: parseFloat(temperatureSlider.value),
            exaggeration: parseFloat(exaggerationSlider.value),
            cfg_weight: parseFloat(cfgWeightSlider.value),
            speed_factor: parseFloat(speedFactorSlider.value),
            seed: parseInt(seedInput.value, 10),
            language: languageSelect.value,
            voice_mode: currentVoiceMode,
            split_text: splitTextToggle.checked,
            chunk_size: parseInt(chunkSizeSlider.value, 10),
            output_format: outputFormatSelect.value || 'mp3'
        };
        if (currentVoiceMode === 'predefined' && predefinedVoiceSelect.value !== 'none') {
            jsonData.predefined_voice_id = predefinedVoiceSelect.value;
        } else if (currentVoiceMode === 'clone' && cloneReferenceSelect.value !== 'none') {
            jsonData.reference_audio_filename = cloneReferenceSelect.value;
        }
        return jsonData;
    }

    async function submitTTSRequest() {
        isGenerating = true;
        showLoadingOverlay();
        const startTime = performance.now();
        const jsonData = getTTSFormData();
        try {
            const response = await fetch(`${API_BASE_URL}/tts`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(jsonData)
            });
            if (!response.ok) {
                const errorResult = await response.json().catch(() => ({ detail: `HTTP error ${response.status}` }));
                throw new Error(errorResult.detail || 'TTS generation failed.');
            }
            const audioBlob = await response.blob();
            const endTime = performance.now();
            const genTime = ((endTime - startTime) / 1000).toFixed(2);
            const filenameFromServer = response.headers.get('Content-Disposition')?.split('filename=')[1]?.replace(/"/g, '') || 'generated_audio.wav';
            const resultDetails = {
                outputUrl: URL.createObjectURL(audioBlob), filename: filenameFromServer, genTime: genTime,
                submittedVoiceMode: jsonData.voice_mode, submittedPredefinedVoice: jsonData.predefined_voice_id,
                submittedCloneFile: jsonData.reference_audio_filename
            };
            initializeWaveSurfer(resultDetails.outputUrl, resultDetails);
            showNotification('Audio generated successfully!', 'success');
        } catch (error) {
            console.error('TTS Generation Error:', error);
            showNotification(error.message || 'An unknown error occurred during TTS generation.', 'error');
        } finally {
            isGenerating = false;
            hideLoadingOverlay();
        }
    }

    function proceedWithSubmissionChecks() {
        const textContent = textArea.value.trim();
        const isSplittingEnabled = splitTextToggle.checked;
        const currentChunkSz = parseInt(chunkSizeSlider.value, 10);
        const needsChunkWarn = isSplittingEnabled && textContent.length >= currentChunkSz * 1.5 &&
            currentVoiceMode !== 'predefined' && currentVoiceMode !== 'clone' &&
            (!seedInput || parseInt(seedInput.value, 10) === 0 || seedInput.value === '') && !hideChunkWarning;
        if (needsChunkWarn) { showChunkWarningModal(); return; }
        submitTTSRequest();
    }

    // --- Attach main generation event to the button's CLICK, not the form's SUBMIT ---
    // This is a more robust method that prevents accidental submissions during page load.
    if (generateBtn) {
        generateBtn.addEventListener('click', function (event) {

            console.log('Generate button clicked!');
            console.log('Current voice mode:', currentVoiceMode);
            console.log('Is generating:', isGenerating);
            console.log('Text content:', textArea ? textArea.value.trim() : 'NO TEXTAREA');

            // We still prevent default in case the button has any default browser actions.
            event.preventDefault();

            if (isGenerating) {
                showNotification("Generation is already in progress.", "warning");
                return;
            }
            const textContent = textArea.value.trim();
            if (!textContent) {
                showNotification("Please enter some text to generate speech.", 'error');
                return;
            }
            if (currentVoiceMode === 'predefined' && (!predefinedVoiceSelect || predefinedVoiceSelect.value === 'none')) {
                showNotification("Please select a predefined voice.", 'error');
                return;
            }
            if (currentVoiceMode === 'clone' && (!cloneReferenceSelect || cloneReferenceSelect.value === 'none')) {
                showNotification("Please select a reference audio file for Voice Cloning.", 'error');
                return;
            }

            // Check for the generation quality warning.
            if (!hideGenerationWarning) {
                showGenerationWarningModal();
                return; // Stop here and let the modal handler take over.
            }

            // If the warning is hidden, proceed to the final checks.
            proceedWithSubmissionChecks();
        });
    } else {
        console.log('Generate button not found!');
    }

    // --- Modal Handling ---
    function showChunkWarningModal() {
        if (chunkWarningModal) {
            chunkWarningModal.style.display = 'flex';
            chunkWarningModal.classList.remove('hidden', 'opacity-0');
            chunkWarningModal.dataset.state = 'open';
        }
    }
    function hideChunkWarningModal() {
        if (chunkWarningModal) {
            chunkWarningModal.classList.add('opacity-0');
            setTimeout(() => {
                chunkWarningModal.style.display = 'none';
                chunkWarningModal.dataset.state = 'closed';
            }, 300);
        }
    }
    function showGenerationWarningModal() {
        if (generationWarningModal) {
            generationWarningModal.style.display = 'flex';
            generationWarningModal.classList.remove('hidden', 'opacity-0');
            generationWarningModal.dataset.state = 'open';
        }
    }
    function hideGenerationWarningModal() {
        if (generationWarningModal) {
            generationWarningModal.classList.add('opacity-0');
            setTimeout(() => {
                generationWarningModal.style.display = 'none';
                generationWarningModal.dataset.state = 'closed';
            }, 300);
        }
    }
    if (chunkWarningOkBtn) chunkWarningOkBtn.addEventListener('click', () => {
        if (hideChunkWarningCheckbox && hideChunkWarningCheckbox.checked) hideChunkWarning = true;
        hideChunkWarningModal(); debouncedSaveState(); submitTTSRequest();
    });
    if (chunkWarningCancelBtn) chunkWarningCancelBtn.addEventListener('click', hideChunkWarningModal);
    if (generationWarningAcknowledgeBtn) generationWarningAcknowledgeBtn.addEventListener('click', () => {
        if (hideGenerationWarningCheckbox && hideGenerationWarningCheckbox.checked) hideGenerationWarning = true;
        hideGenerationWarningModal(); debouncedSaveState(); proceedWithSubmissionChecks();
    });
    if (loadingCancelBtn) loadingCancelBtn.addEventListener('click', () => {
        if (isGenerating) { isGenerating = false; hideLoadingOverlay(); showNotification("Generation UI cancelled by user.", "info"); }
    });
    function showLoadingOverlay() {
        if (loadingOverlay && generateBtn && loadingCancelBtn) {
            loadingMessage.textContent = 'Generating audio...';
            loadingStatusText.textContent = 'Please wait. This may take some time.';
            loadingOverlay.style.display = 'flex';
            loadingOverlay.classList.remove('hidden', 'opacity-0'); loadingOverlay.dataset.state = 'open';
            generateBtn.disabled = true; loadingCancelBtn.disabled = false;
        }
    }
    function hideLoadingOverlay() {
        if (loadingOverlay && generateBtn) {
            loadingOverlay.classList.add('opacity-0');
            setTimeout(() => {
                loadingOverlay.style.display = 'none';
                loadingOverlay.dataset.state = 'closed';
            }, 300);
            generateBtn.disabled = false;
        }
    }

    // --- Configuration Management ---
    function displayServerConfiguration() {
        if (!serverConfigForm || !currentConfig || Object.keys(currentConfig).length === 0) return;
        const fieldsToDisplay = {
            "server.host": currentConfig.server?.host, "server.port": currentConfig.server?.port,
            "tts_engine.device": currentConfig.tts_engine?.device, "tts_engine.default_voice_id": currentConfig.tts_engine?.default_voice_id,
            "paths.model_cache": currentConfig.paths?.model_cache, "tts_engine.predefined_voices_path": currentConfig.tts_engine?.predefined_voices_path,
            "tts_engine.reference_audio_path": currentConfig.tts_engine?.reference_audio_path, "paths.output": currentConfig.paths?.output,
            "audio_output.format": currentConfig.audio_output?.format, "audio_output.sample_rate": currentConfig.audio_output?.sample_rate
        };
        for (const name in fieldsToDisplay) {
            const input = serverConfigForm.querySelector(`input[name="${name}"]`);
            if (input) {
                input.value = fieldsToDisplay[name] !== undefined ? fieldsToDisplay[name] : '';
                if (name.includes('.host') || name.includes('.port') || name.includes('.device') || name.includes('paths.')) input.readOnly = true;
                else input.readOnly = false;
            }
        }
    }
    async function updateConfigStatus(button, statusElem, message, type = 'info', duration = 5000, enableButtonAfter = true) {
        const statusClasses = { success: 'text-green-600 dark:text-green-400', error: 'text-red-600 dark:text-red-400', warning: 'text-yellow-600 dark:text-yellow-400', info: 'text-indigo-600 dark:text-indigo-400', processing: 'text-yellow-600 dark:text-yellow-400 animate-pulse' };
        const isProcessing = message.toLowerCase().includes('saving') || message.toLowerCase().includes('restarting') || message.toLowerCase().includes('resetting');
        const messageType = isProcessing ? 'processing' : type;
        if (statusElem) {
            statusElem.textContent = message;
            statusElem.className = `text-xs ml-2 ${statusClasses[messageType] || statusClasses['info']}`;
            statusElem.classList.remove('hidden');
        }
        if (button) button.disabled = isProcessing || (type === 'error' && !enableButtonAfter) || (type === 'success' && !enableButtonAfter);
        if (duration > 0) setTimeout(() => { if (statusElem) statusElem.classList.add('hidden'); if (button && enableButtonAfter) button.disabled = false; }, duration);
        else if (button && enableButtonAfter && !isProcessing) button.disabled = false;
    }

    if (saveConfigBtn && configStatus) {
        saveConfigBtn.addEventListener('click', async () => {
            const configDataToSave = {};
            const inputs = serverConfigForm.querySelectorAll('input[name]:not([readonly]), select[name]:not([readonly])');
            inputs.forEach(input => {
                const keys = input.name.split('.'); let currentLevel = configDataToSave;
                keys.forEach((key, index) => {
                    if (index === keys.length - 1) {
                        let value = input.value;
                        if (input.type === 'number') value = parseFloat(value) || 0;
                        else if (input.type === 'checkbox') value = input.checked;
                        currentLevel[key] = value;
                    } else { currentLevel[key] = currentLevel[key] || {}; currentLevel = currentLevel[key]; }
                });
            });
            if (Object.keys(configDataToSave).length === 0) { showNotification("No editable configuration values to save.", "info"); return; }
            updateConfigStatus(saveConfigBtn, configStatus, 'Saving configuration...', 'info', 0, false);
            try {
                const response = await fetch(`${API_BASE_URL}/save_settings`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(configDataToSave)
                });
                const result = await response.json();
                if (!response.ok) throw new Error(result.detail || 'Failed to save configuration');
                updateConfigStatus(saveConfigBtn, configStatus, result.message || 'Configuration saved.', 'success', 5000);
                if (result.restart_needed && restartServerBtn) restartServerBtn.classList.remove('hidden');
                await fetchInitialData();
                showNotification("Configuration saved. Some changes may require a server restart if prompted.", "success");
            } catch (error) {
                console.error('Error saving server config:', error);
                updateConfigStatus(saveConfigBtn, configStatus, `Error: ${error.message}`, 'error', 0);
            }
        });
    }

    if (saveGenDefaultsBtn && genDefaultsStatus) {
        saveGenDefaultsBtn.addEventListener('click', async () => {
            const genParams = {
                temperature: parseFloat(temperatureSlider.value), exaggeration: parseFloat(exaggerationSlider.value),
                cfg_weight: parseFloat(cfgWeightSlider.value), speed_factor: parseFloat(speedFactorSlider.value),
                seed: parseInt(seedInput.value, 10) || 0, language: languageSelect.value
            };
            updateConfigStatus(saveGenDefaultsBtn, genDefaultsStatus, 'Saving generation defaults...', 'info', 0, false);
            try {
                const response = await fetch(`${API_BASE_URL}/save_settings`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ generation_defaults: genParams })
                });
                const result = await response.json();
                if (!response.ok) throw new Error(result.detail || 'Failed to save generation defaults');
                updateConfigStatus(saveGenDefaultsBtn, genDefaultsStatus, result.message || 'Generation defaults saved.', 'success', 5000);
                if (currentConfig.generation_defaults) Object.assign(currentConfig.generation_defaults, genParams);
            } catch (error) {
                console.error('Error saving generation defaults:', error);
                updateConfigStatus(saveGenDefaultsBtn, genDefaultsStatus, `Error: ${error.message}`, 'error', 0);
            }
        });
    }

    if (resetSettingsBtn) {
        resetSettingsBtn.addEventListener('click', async () => {
            if (!confirm("Are you sure you want to reset ALL settings to their initial defaults? This will affect config.yaml and UI preferences. This action cannot be undone.")) return;
            updateConfigStatus(resetSettingsBtn, configStatus, 'Resetting settings...', 'info', 0, false);
            try {
                const response = await fetch(`${API_BASE_URL}/reset_settings`, {
                    method: 'POST'
                });
                if (!response.ok) {
                    const errorResult = await response.json().catch(() => ({ detail: 'Failed to reset settings on server.' }));
                    throw new Error(errorResult.detail);
                }
                const result = await response.json();
                updateConfigStatus(resetSettingsBtn, configStatus, result.message + " Reloading page...", 'success', 0, false);
                setTimeout(() => window.location.reload(true), 2000);
            } catch (error) {
                console.error('Error resetting settings:', error);
                updateConfigStatus(resetSettingsBtn, configStatus, `Reset Error: ${error.message}`, 'error', 0);
                showNotification(`Error resetting settings: ${error.message}`, 'error');
            }
        });
    }

    if (restartServerBtn) {
        restartServerBtn.addEventListener('click', async () => {
            if (!confirm("Are you sure you want to restart the server?")) return;
            updateConfigStatus(restartServerBtn, configStatus, 'Attempting server restart...', 'processing', 0, false);
            try {
                const response = await fetch(`${API_BASE_URL}/restart_server`, {
                    method: 'POST'
                });
                const result = await response.json();
                if (!response.ok) throw new Error(result.detail || 'Server responded with error on restart command');
                showNotification("Server restart initiated. Please wait a moment for the server to come back online, then refresh the page.", "info", 10000);
            } catch (error) {
                showNotification(`Server restart command failed: ${error.message}`, "error");
                updateConfigStatus(restartServerBtn, configStatus, `Restart failed.`, 'error', 5000, true);
            }
        });
    }

    // --- File Upload & Refresh ---
    async function handleFileUpload(fileInput, endpoint, successCallback, buttonToAnimate) {
        const files = fileInput.files;
        if (!files || files.length === 0) return;
        const originalButtonHTML = buttonToAnimate ? buttonToAnimate.innerHTML : '';
        if (buttonToAnimate) {
            buttonToAnimate.innerHTML = `<svg class="animate-spin h-5 w-5 mr-1.5 inline-block" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>Uploading...`;
            buttonToAnimate.disabled = true;
        }
        const uploadNotification = showNotification(`Uploading ${files.length} file(s)...`, 'info', 0);
        const formData = new FormData();
        for (const file of files) formData.append('files', file);
        try {
            const response = await fetch(`${API_BASE_URL}${endpoint}`, {
                method: 'POST',
                body: formData
            });
            const result = await response.json();
            if (uploadNotification) uploadNotification.remove();
            if (!response.ok) throw new Error(result.message || result.detail || `Upload failed with status ${response.status}`);
            if (result.errors && result.errors.length > 0) {
                result.errors.forEach(err => showNotification(`Upload Warning: ${err.filename || 'File'} - ${err.error}`, 'warning', 10000));
            }
            const successfulUploads = result.uploaded_files || [];
            if (successfulUploads.length > 0) {
                showNotification(`Successfully uploaded: ${successfulUploads.join(', ')}`, 'success');
            } else if (!result.errors || result.errors.length === 0) {
                showNotification("Files processed. No new valid files were added or an issue occurred.", 'info');
            }
            successCallback(result);
            debouncedSaveState();
        } catch (error) {
            console.error(`Error uploading to ${endpoint}:`, error);
            if (uploadNotification) uploadNotification.remove();
            showNotification(`Upload Error: ${error.message}`, 'error');
        } finally {
            if (buttonToAnimate) {
                buttonToAnimate.disabled = false;
                buttonToAnimate.innerHTML = originalButtonHTML;
            }
            fileInput.value = '';
        }
    }

    if (cloneImportButton && cloneFileInput) {
        cloneImportButton.addEventListener('click', () => cloneFileInput.click());
        cloneFileInput.addEventListener('change', () => handleFileUpload(cloneFileInput, '/upload_reference', (result) => {
            initialReferenceFiles = result.all_reference_files || [];
            populateReferenceFiles();
            const firstUploaded = result.uploaded_files?.[0];
            if (firstUploaded && cloneReferenceSelect && Array.from(cloneReferenceSelect.options).some(opt => opt.value === firstUploaded)) {
                cloneReferenceSelect.value = firstUploaded;
            }
        }, cloneImportButton));
    }

    if (predefinedVoiceImportButton && predefinedVoiceFileInput) {
        predefinedVoiceImportButton.addEventListener('click', () => predefinedVoiceFileInput.click());
        predefinedVoiceFileInput.addEventListener('change', () => handleFileUpload(predefinedVoiceFileInput, '/upload_predefined_voice', (result) => {
            initialPredefinedVoices = result.all_predefined_voices || [];
            populatePredefinedVoices();
            const firstUploadedFilename = result.uploaded_files?.[0];
            if (firstUploadedFilename && predefinedVoiceSelect && initialPredefinedVoices.some(v => v.filename === firstUploadedFilename)) {
                predefinedVoiceSelect.value = firstUploadedFilename;
            }
        }, predefinedVoiceImportButton));
    }

    if (cloneRefreshButton && cloneReferenceSelect) {
        cloneRefreshButton.addEventListener('click', async () => {
            const originalButtonIcon = cloneRefreshButton.innerHTML;
            cloneRefreshButton.innerHTML = `<svg class="animate-spin h-5 w-5" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>`;
            cloneRefreshButton.disabled = true;
            try {
                const response = await fetch(`${API_BASE_URL}/get_reference_files`);
                if (!response.ok) throw new Error('Failed to fetch reference files list');
                const files = await response.json();
                initialReferenceFiles = files;
                populateReferenceFiles();
                showNotification("Reference file list refreshed.", 'info', 2000);
                debouncedSaveState();
            } catch (error) {
                console.error("Error refreshing reference files:", error);
                showNotification(`Error refreshing list: ${error.message}`, 'error');
            } finally {
                cloneRefreshButton.disabled = false;
                cloneRefreshButton.innerHTML = originalButtonIcon;
            }
        });
    }

    if (predefinedVoiceRefreshButton && predefinedVoiceSelect) {
        predefinedVoiceRefreshButton.addEventListener('click', async () => {
            const originalButtonIcon = predefinedVoiceRefreshButton.innerHTML;
            predefinedVoiceRefreshButton.innerHTML = `<svg class="animate-spin h-5 w-5" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>`;
            predefinedVoiceRefreshButton.disabled = true;
            try {
                const response = await fetch(`${API_BASE_URL}/get_predefined_voices`);
                if (!response.ok) throw new Error('Failed to fetch predefined voices list');
                const voices = await response.json();
                initialPredefinedVoices = voices;
                populatePredefinedVoices();
                showNotification("Predefined voices list refreshed.", 'info', 2000);
                debouncedSaveState();
            } catch (error) {
                console.error("Error refreshing predefined voices:", error);
                showNotification(`Error refreshing list: ${error.message}`, 'error');
            } finally {
                predefinedVoiceRefreshButton.disabled = false;
                predefinedVoiceRefreshButton.innerHTML = originalButtonIcon;
            }
        });
    }

    // Call fetchInitialData at the end of setup to kick everything off.
    // Note: This calls initializeApplication internally.
    await fetchInitialData();
});
