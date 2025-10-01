#!/usr/bin/env node

/**
 * Debate abierto CON Grok - Le damos la palabra para que cuestione H1SDR
 */

require('dotenv').config();
const { chromium } = require('playwright');
const AIAdapters = require('./ai-adapters');

async function openDebateWithGrok() {
    console.log('🤖 Claude abriendo debate abierto CON Grok sobre H1SDR...\n');

    let browser, adapters;

    try {
        browser = await chromium.connectOverCDP('http://localhost:9222');
        console.log('✅ Conectado a navegador\n');

        const contexts = browser.contexts();
        const page = contexts[0].pages()[0];

        if (!page.url().includes('grok.com')) {
            await page.goto('https://grok.com', { waitUntil: 'load', timeout: 30000 });
            await page.waitForTimeout(5000);
        }

        console.log(`📍 En: ${page.url()}\n`);

        adapters = new AIAdapters(browser, page);

        const prompt = `Grok, ahora es tu turno. Hemos debatido arquitectura, pero H1SDR tiene muchos más aspectos. Te presento el estado actual del proyecto:

**H1SDR v1.0 - Estado Actual:**

**Backend (Python FastAPI):**
\`\`\`
src/web_sdr/
├── main.py              # FastAPI server, WebSocket streams
├── config.py            # 16 band presets (H1, OH lines, amateur, broadcast)
├── controllers/         # RTL-SDR hardware interface
├── dsp/                 # FFTW FFT, AM/FM/USB/LSB/CW demod
├── services/            # WebSocket connection management
└── models/              # Pydantic data models
\`\`\`

**Frontend (HTML5/WebGL):**
\`\`\`
web/
├── index.html           # Monolithic UI (all controls in one page)
├── js/
│   ├── init.js          # Initialization, event handlers (1800+ lines)
│   ├── config.js        # Band configurations
│   ├── components/      # Spectrum, waterfall, controls
│   ├── services/        # WebSocket client, audio
│   └── audio-worklet.js # Web Audio API processing
└── css/                 # Styling
\`\`\`

**Características Actuales:**
- ✅ Real-time spectrum @ 20 FPS (FFTW 4096 FFT)
- ✅ 5 demod modes funcionales sin dropouts
- ✅ WebGL visualization fluida
- ✅ 16 bandas preset
- ✅ Scanner FM automático
- ✅ Frequency control coherente (single source of truth)
- ✅ Resizable layout
- ✅ Playwright automation para testing

**Problemas Conocidos:**
- ⚠️ init.js es gigante (1800 lines) - mantenibilidad
- ⚠️ No hay recording/playback
- ⚠️ No hay RFI rejection
- ⚠️ No hay export FITS
- ⚠️ Frontend no usa framework (vanilla JS)
- ⚠️ No hay state management formal
- ⚠️ WebSocket reconnection manual
- ⚠️ No hay tests unitarios (solo E2E con Playwright)

**AHORA TE TOCA A TI:**

**1. ¿Qué aspectos NO hemos debatido que son críticos?**
   - Frontend architecture? (¿React? ¿Vue? ¿Vanilla?)
   - Testing strategy?
   - Deployment? (Docker, systemd?)
   - Security?
   - Documentation?
   - Performance profiling?

**2. ¿Qué preguntas DEBERÍAS hacerme sobre el diseño actual?**
   - ¿Cosas que no tienen sentido?
   - ¿Decisiones cuestionables?
   - ¿Missing features obvios?

**3. ¿Qué opinas del código existente que viste en la sesión anterior?**
   - init.js con 1800 lines
   - Estructura de directorios
   - Separación de responsabilidades

**4. Si tuvieras que revisar este proyecto como code reviewer, ¿cuáles serían tus 5 comentarios principales?**

**5. ¿Qué aspectos de radioastronomía específicos estamos ignorando?**
   - Calibración?
   - Doppler correction automática?
   - Integration time optimization?
   - Baseline correction?

**TU TURNO:** Hazme las preguntas incómodas. Critica lo que no te guste. Señala lo que falta. Sé el arquitecto senior que revisa mi código.

No te limites a responder - **CUESTIONA, PREGUNTA, DEBATE**.`;

        console.log('📤 Enviando apertura de debate a Grok...\n');
        console.log('━'.repeat(60));
        console.log(prompt);
        console.log('━'.repeat(60));
        console.log('\n⏳ Esperando preguntas y críticas de Grok...\n');

        const result = await adapters.grokAdapter(prompt, {
            maxRetries: 1,
            navigationTimeout: 30000,
            responseTimeout: 180000
        });

        console.log('\n' + '═'.repeat(60));
        if (result.success) {
            console.log('✅ PREGUNTAS Y CRÍTICAS DE GROK:');
            console.log('═'.repeat(60));
            console.log(result.response);
            console.log('═'.repeat(60));
        } else {
            console.log('❌ Error:', result.error);
            console.log('═'.repeat(60));
        }

        console.log('\n💬 Debate abierto iniciado.');
        console.log('   Presiona Ctrl+C para salir.\n');

        await new Promise(() => {});

    } catch (error) {
        console.error('\n❌ Error:', error.message);
        console.error(error.stack);
    }
}

openDebateWithGrok().catch(console.error);
