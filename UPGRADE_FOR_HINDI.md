# Upgrade Guide: Enable Hindi & Multilingual Support

## Current Status

Your Chatterbox TTS server is currently running with:
- **chatterbox-tts version**: 0.1.2 (English-only)
- **Model**: English-only TTS model
- **Languages**: English only

## To Enable Hindi & 22 Other Languages

The code has been updated to support multilingual TTS, but you need to upgrade the `chatterbox-tts` package to access the multilingual model.

### Step 1: Upgrade chatterbox-tts Package

```bash
# Stop the server first (Ctrl+C if running)

# Activate your virtual environment
source .venv/bin/activate

# Upgrade to the latest version
pip install --upgrade chatterbox-tts

# Or install a specific version if available
pip install chatterbox-tts>=0.1.4
```

### Step 2: Verify the Upgrade

```bash
# Check the installed version
pip show chatterbox-tts

# Verify multilingual support is available
python -c "from chatterbox import ChatterboxMultilingualTTS; print('Multilingual support: Available')" || echo "Multilingual support: Not yet available"
```

### Step 3: Enable Multilingual in Configuration

Edit `config.yaml`:

```yaml
model:
  repo_id: ResembleAI/chatterbox
  use_multilingual: true  # Change from false to true

generation_defaults:
  temperature: 0.8
  exaggeration: 0.5
  cfg_weight: 0.5
  seed: 0
  speed_factor: 1.0
  language: hi  # Change from 'en' to 'hi' for Hindi
```

### Step 4: Restart the Server

```bash
./run.bash
```

Or manually:

```bash
source .venv/bin/activate
python server.py
```

### Step 5: Verify Hindi Support

Check the server logs for:
```
Successfully loaded Multilingual TTS model on mps. Supports 23 languages including Hindi.
```

Open the web UI and you should see:
- Model badge showing: "🌐 Multilingual (23 Languages)"
- Language selector with Hindi (hi) as default

## Current Fallback Behavior

The code has been designed to gracefully handle the missing multilingual model:

1. **If multilingual is requested but not available**:
   - Server logs a warning
   - Automatically falls back to English-only model
   - Server continues to run normally

2. **If you try to generate Hindi audio**:
   - Server logs a warning: "Language 'hi' requested but multilingual model not available"
   - Generates English audio instead
   - No errors or crashes

## Supported Languages (After Upgrade)

Once upgraded, your server will support these 23 languages:

| Code | Language | Code | Language | Code | Language |
|------|----------|------|----------|------|----------|
| ar | Arabic | da | Danish | de | German |
| el | Greek | en | English | es | Spanish |
| fi | Finnish | fr | French | he | Hebrew |
| **hi** | **Hindi** | it | Italian | ja | Japanese |
| ko | Korean | ms | Malay | nl | Dutch |
| no | Norwegian | pl | Polish | pt | Portuguese |
| ru | Russian | sv | Swedish | sw | Swahili |
| tr | Turkish | zh | Chinese | | |

## Troubleshooting

### Issue: Multilingual import still fails after upgrade

**Solution**: The multilingual model might be in a different package or version:

```bash
# Check if there's a separate multilingual package
pip search chatterbox-multilingual

# Or check the Chatterbox GitHub for latest installation instructions
# https://github.com/resemble-ai/chatterbox
```

### Issue: Model download fails

**Solution**: The multilingual model is larger (~2-3GB). Ensure you have:
- Sufficient disk space
- Stable internet connection
- Access to Hugging Face (not blocked by firewall)

### Issue: Server shows "Multilingual model requested but not available"

This means the package doesn't have the multilingual class yet. Check:

```bash
# Verify the package contents
python -c "import chatterbox; print(dir(chatterbox))"

# Look for ChatterboxMultilingualTTS in the output
```

### Issue: Still generating English audio for Hindi text

Possible causes:
1. Multilingual model not loaded (check logs)
2. Config still has `use_multilingual: false`
3. Model badge still shows "English Only"

**Solution**: Follow all upgrade steps again and restart server.

## Alternative: Use Latest GitHub Version

If PyPI doesn't have the latest multilingual version yet:

```bash
# Install directly from GitHub
pip uninstall chatterbox-tts -y
pip install git+https://github.com/resemble-ai/chatterbox.git

# Or clone and install locally
git clone https://github.com/resemble-ai/chatterbox.git
cd chatterbox
pip install -e .
```

## Rollback to English-Only

If you prefer to use only English:

1. Edit `config.yaml`:
   ```yaml
   model:
     use_multilingual: false
   
   generation_defaults:
     language: en
   ```

2. Restart server

The server will use the smaller, faster English-only model.

## Code Changes Summary

The following changes were made to support gradual migration:

### engine.py
- Added conditional import for multilingual model
- Falls back gracefully if multilingual not available
- Warns user to upgrade when multilingual is requested
- Uses English-only model as fallback

### config.yaml
- Added `model.use_multilingual` setting (currently `false`)
- Language default set to `en` (will be `hi` after upgrade)

### UI
- Model selector dropdown to switch between models
- Status badge showing currently loaded model
- Language selector for all 23 languages
- Automatic warnings when changes require restart

## Benefits After Upgrade

✅ **Full Hindi Support** - Generate natural-sounding Hindi speech
✅ **22 Additional Languages** - Support for multiple languages
✅ **Better Quality** - Improved voice quality for non-English languages
✅ **No Accent Issues** - Native language synthesis without English accent
✅ **UI Ready** - All UI controls already in place

## Next Steps

1. Upgrade `chatterbox-tts` package
2. Update `config.yaml` settings
3. Restart server
4. Test Hindi generation
5. Enjoy multilingual TTS! 🎉

---

**Need Help?**
- Check server logs for detailed error messages
- Review [Chatterbox GitHub](https://github.com/resemble-ai/chatterbox)
- Check [Chatterbox Multilingual Demo](https://huggingface.co/spaces/ResembleAI/Chatterbox-Multilingual-TTS)
