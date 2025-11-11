# UI Changes for Multilingual Support

## Summary
Added UI controls to allow users to select between the multilingual and English-only TTS models, along with improved language selection and status indicators.

## Changes Made

### 1. Navigation Bar (index.html)
**Added Model Status Badge** - Shows which model is currently loaded
- Location: Next to the title in the navigation bar
- Displays: "🌐 Multilingual (23 Languages)" or "🇬🇧 English Only"
- Updates automatically based on server configuration
- Provides visual feedback about the active model

### 2. Generation Parameters Section (index.html)
**Added Model Type Selector** - Dropdown to choose TTS model
- Location: Just before the Language selector in the Generation Parameters
- Options:
  - "Multilingual (23 Languages)" - Supports 23 languages including Hindi
  - "English Only" - Smaller model, English only
- Note: Warns users that server restart is required to apply changes

**Updated Language Selector**
- Changed default selection from "en" (English) to "hi" (Hindi)
- Added language codes in parentheses for clarity (e.g., "Hindi (hi)")
- Updated help text to be more informative
- Now properly syncs with the config.yaml default language setting

### 3. JavaScript Updates (script.js)

#### Model Type Handling
- Added `modelTypeSelect` element reference
- Loads current model type from server config on page load
- Sets dropdown value based on `config.model.use_multilingual`

#### Save Generation Parameters
- Extended to save both generation parameters AND model type selection
- Saves `model.use_multilingual` boolean value to server config
- Shows warning notification when model type changes
- Detects if restart is needed and notifies user

#### Model Status Badge Updates
- Badge text and icon update on page load based on config
- Shows multilingual status with globe emoji (🌐) or English with flag (🇬🇧)
- Tooltip provides detailed information about loaded model

#### Change Detection & Warnings
- Detects when user changes model type from current config
- Shows persistent notification reminding user to:
  1. Click "Save Generation Parameters"
  2. Restart the server for changes to take effect
- Prevents confusion about why model didn't change

## User Workflow

### To Switch Models:
1. Open the UI in browser
2. Look at the Generation Parameters section
3. Find "TTS Model" dropdown
4. Select desired model:
   - "Multilingual (23 Languages)" - for Hindi and other languages
   - "English Only" - for English-only use case
5. Click "Save Generation Parameters" button
6. Notice the warning about server restart
7. Click "Restart Server" button (or manually restart)
8. Refresh the page
9. Verify the model status badge shows the new model

### To Use Hindi (Default):
1. Model is already set to Multilingual
2. Language is already set to Hindi (hi)
3. Simply enter Hindi text and generate

### To Use Other Languages:
1. Ensure Model Type is "Multilingual"
2. Select desired language from Language dropdown
3. Enter text in that language
4. Generate speech

## Visual Indicators

### Model Status Badge (Top Navigation)
```
Current State          Badge Display
------------------     -------------------------------
Multilingual loaded -> "🌐 Multilingual (23 Languages)"
English-only loaded -> "🇬🇧 English Only"
```

### Model Type Selector (Form)
```
Config Value                      Dropdown Shows
--------------------------------  ---------------------------
use_multilingual: true        ->  "Multilingual (23 Languages)"
use_multilingual: false       ->  "English Only"
```

### Language Selector (Form)
- Shows all 23 supported languages
- Hindi (hi) is selected by default
- Language codes shown for clarity

## Benefits

1. **User-Friendly**: Clear visual feedback about which model is loaded
2. **Flexible**: Easy switching between multilingual and English-only models
3. **Informative**: Warnings and tooltips guide users through the process
4. **Consistent**: UI state syncs with server configuration
5. **Safe**: Clear warnings about server restart requirements

## Technical Details

### Config Values Saved
```json
{
  "model": {
    "use_multilingual": true  // or false
  },
  "generation_defaults": {
    "language": "hi",  // or any of 23 supported codes
    "temperature": 0.8,
    "exaggeration": 0.5,
    // ... other params
  }
}
```

### Supported Language Codes
ar, da, de, el, en, es, fi, fr, he, **hi**, it, ja, ko, ms, nl, no, pl, pt, ru, sv, sw, tr, zh

### Files Modified
1. `ui/index.html` - Added model selector, updated language selector, added status badge
2. `ui/script.js` - Added model handling logic, status updates, change detection
3. `config.yaml` - Set default to multilingual model and Hindi language
4. `config.py` - Added default multilingual setting to DEFAULT_CONFIG
5. `engine.py` - Added multilingual model support
6. `server.py` - Added language_id parameter handling

## Testing Checklist

- [ ] Model status badge shows correct model on page load
- [ ] Model type selector reflects current config
- [ ] Language selector defaults to Hindi
- [ ] Changing model type shows notification
- [ ] Save button updates config.yaml correctly
- [ ] Restart button triggers server restart
- [ ] After restart, new model is loaded
- [ ] Badge updates after model change
- [ ] Hindi text generates proper speech (not noise)
- [ ] Other languages work correctly
- [ ] English still works when English-only model selected
