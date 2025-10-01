#!/usr/bin/env node

/**
 * Consultar a Grok sobre mejoras para H1SDR WebSDR
 */

require('dotenv').config();
const { chromium } = require('playwright');
const AIAdapters = require('./ai-adapters');

async function consultGrokH1SDR() {
    console.log('🤖 Claude consultando a Grok sobre H1SDR WebSDR...\n');

    let browser, adapters;

    try {
        // Conectar al navegador existente
        browser = await chromium.connectOverCDP('http://localhost:9222');
        console.log('✅ Conectado a navegador\n');

        const contexts = browser.contexts();
        const context = contexts[0];
        const pages = context.pages();
        const page = pages[0];

        // Navegar a Grok si no estamos ahí
        if (!page.url().includes('grok.com')) {
            console.log('📍 Navegando a Grok...');
            await page.goto('https://grok.com', { waitUntil: 'load', timeout: 30000 });
            await page.waitForTimeout(5000);
        }

        console.log(`📍 En: ${page.url()}\n`);

        // Crear adaptador
        adapters = new AIAdapters(browser, page);

        // Mensaje a Grok sobre H1SDR
        const prompt = `Hola Grok, soy Claude (Anthropic). Estoy trabajando con Pablo en un proyecto de radioastronomía llamado H1SDR - un WebSDR moderno para detectar la línea de hidrógeno a 1420 MHz y operaciones multibanda con RTL-SDR.

**Stack Actual:**
- Backend: FastAPI (Python) con WebSocket streaming
- Frontend: HTML5/WebGL para espectro + Web Audio API para demod
- DSP: FFTW-acelerado, 4096 FFT @ 20 FPS
- Hardware: RTL-SDR Blog V4 (24-1766 MHz)
- Modos: AM/FM/USB/LSB/CW/SPECTRUM

**Completado Recientemente:**
- ✅ Audio continuo sin dropouts (fix de doble resampling)
- ✅ 16 bandas preset (radioastronomía, amateur, broadcast)
- ✅ Control de frecuencia coherente (single source of truth)
- ✅ Scanner FM automático
- ✅ Layout resizable con controles de intensidad
- ✅ Playwright automation para testing

**Áreas Identificadas para Mejora:**
1. Recording/playback (IQ y audio)
2. Integración scanner con análisis espectral real
3. RFI rejection avanzado
4. Export FITS con WCS headers (astronomía)
5. Mobile app companion
6. Multi-receiver correlation
7. ML signal classification

**Pregunta:**
¿Qué 5 mejoras técnicas priorizarías para este proyecto WebSDR de radioastronomía? Considera:
- Utilidad para observaciones astronómicas serias
- Experiencia de usuario para radioaficionados
- Performance en tiempo real
- Innovación técnica vs complejidad

Sé conciso y práctico con ejemplos de implementación.`;

        console.log('📤 Enviando consulta a Grok...\n');
        console.log('━'.repeat(60));
        console.log(prompt);
        console.log('━'.repeat(60));
        console.log('\n⏳ Esperando respuesta de Grok...\n');

        const result = await adapters.grokAdapter(prompt, {
            maxRetries: 1,
            navigationTimeout: 30000,
            responseTimeout: 120000  // 2 minutos para respuesta más larga
        });

        console.log('\n' + '═'.repeat(60));
        if (result.success) {
            console.log('✅ RESPUESTA DE GROK:');
            console.log('═'.repeat(60));
            console.log(result.response);
            console.log('═'.repeat(60));
        } else {
            console.log('❌ Error:', result.error);
            console.log('═'.repeat(60));
        }

        console.log('\n💬 Conversación completada.');
        console.log('   Presiona Ctrl+C para salir.\n');

        // Mantener abierto
        await new Promise(() => {});

    } catch (error) {
        console.error('\n❌ Error:', error.message);
        console.error(error.stack);
    }
}

consultGrokH1SDR().catch(console.error);
