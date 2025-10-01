#!/usr/bin/env node

/**
 * Consultar a Grok sobre arquitectura H1SDR v2.0
 */

require('dotenv').config();
const { chromium } = require('playwright');
const AIAdapters = require('./ai-adapters');

async function consultGrokH1SDRv2() {
    console.log('🤖 Claude consultando a Grok sobre H1SDR v2.0 Architecture...\n');

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

        // Mensaje a Grok sobre arquitectura v2.0
        const prompt = `Hola Grok, continuemos planificando H1SDR. Basándome en tus recomendaciones anteriores (RFI rejection, FITS export, Recording, Scanner avanzado, Multi-receiver correlation), quiero arquitectar H1SDR v2.0 correctamente desde el inicio.

**OBJETIVO:** Crear una nueva versión limpia que integre todas las capacidades desde el diseño, no como parches.

**Componentes Actuales que FUNCIONAN BIEN (reutilizar):**
- ✅ FastAPI + WebSocket streaming (sólido)
- ✅ FFTW DSP pipeline (rápido)
- ✅ Web Audio API demodulación (sin dropouts)
- ✅ WebGL spectrum display (fluido)
- ✅ RTL-SDR controller (estable)
- ✅ 16 bandas preset config (útil)

**Nuevas Capacidades a Integrar desde Diseño:**
1. RFI rejection pipeline (SciPy adaptive filtering)
2. FITS/HDF5 export con metadata astronómica
3. Recording/playback system (IQ + audio)
4. Advanced scanner con ML signal detection
5. Multi-SDR correlation engine

**PREGUNTAS CLAVE:**

**1. Arquitectura de Backend:**
- ¿Cómo estructurar los módulos para que RFI, recording, correlation sean "first-class citizens" no afterthoughts?
- ¿Patrón de diseño recomendado? (¿Pipeline? ¿Plugin architecture? ¿Microservices?)
- ¿Cómo manejar múltiples streams de datos (raw IQ, filtered, audio, recorded)?

**2. Data Flow:**
- ¿Cómo diseñar el flujo: RTL-SDR → RFI filter → FFT → Demod → Recording → Export?
- ¿Dónde insertar taps para recording sin afectar performance real-time?
- ¿Qué formato intermedio usar? (NumPy arrays? Protocol buffers? Arrow?)

**3. Storage Architecture:**
- ¿HDF5 vs FITS vs ambos? ¿Cuándo usar cada uno?
- ¿Cómo estructurar archivos para búsquedas rápidas de observaciones?
- ¿Metadata schema para astronomy + amateur radio use cases?

**4. Frontend Integration:**
- ¿Cómo exponer nuevas features en UI sin sobrecargar?
- ¿WebWorkers para processing pesado?
- ¿Qué datos enviar por WebSocket vs REST?

**5. Development Roadmap:**
- ¿Qué implementar primero para tener "walking skeleton" funcional?
- ¿Cómo migrar datos/configuraciones desde v1?
- ¿Estrategia de testing para cada módulo?

**ENTREGABLE DESEADO:**
- Estructura de directorios propuesta
- Diagrama de arquitectura (texto/ASCII)
- Orden de implementación (fases)
- Decisiones técnicas clave justificadas
- Código skeleton para módulos core

Sé detallado pero pragmático. Prioriza simplicidad y mantenibilidad sobre features innecesarias.`;

        console.log('📤 Enviando consulta a Grok...\n');
        console.log('━'.repeat(60));
        console.log(prompt);
        console.log('━'.repeat(60));
        console.log('\n⏳ Esperando respuesta de Grok...\n');

        const result = await adapters.grokAdapter(prompt, {
            maxRetries: 1,
            navigationTimeout: 30000,
            responseTimeout: 180000  // 3 minutos para respuesta detallada
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

consultGrokH1SDRv2().catch(console.error);
