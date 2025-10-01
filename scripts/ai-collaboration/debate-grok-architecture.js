#!/usr/bin/env node

/**
 * Debate CON Grok sobre puntos cuestionables de su arquitectura H1SDR v2.0
 */

require('dotenv').config();
const { chromium } = require('playwright');
const AIAdapters = require('./ai-adapters');

async function debateWithGrok() {
    console.log('🤖 Claude debatiendo CON Grok sobre arquitectura H1SDR v2.0...\n');

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

        const prompt = `Hola Grok, soy Claude. Analicé tu propuesta de arquitectura para H1SDR v2.0 y tengo algunas críticas constructivas. Debatamos:

**TU PROPUESTA (resumen):**
- Pipeline con plugin architecture
- asyncio.Queue para streams
- Procesamiento secuencial de plugins
- HDF5 + FITS (dual storage)
- NumPy arrays como formato intermedio

**MIS CUESTIONAMIENTOS:**

**1. Plugin Architecture Sequential Processing**
❓ **Problema:** Propones procesar plugins secuencialmente:
\`\`\`python
for plugin in self.plugins:
    data = await plugin.process(data)
\`\`\`

**Crítica:** Con RTL-SDR a 2.4 MSPS generando datos continuos, el procesamiento secuencial podría causar:
- Backpressure en queues
- Pérdida de samples si un plugin es lento
- Latencia acumulativa (RFI filter + recording + scanner + correlation)

**Alternativa:** ¿No sería mejor un patrón **fan-out** donde cada plugin recibe COPIA del stream en paralelo?
\`\`\`python
tasks = [plugin.process(data.copy()) for plugin in self.plugins]
await asyncio.gather(*tasks)
\`\`\`

**2. asyncio.Queue para High-Throughput SDR**
❓ **Problema:** asyncio.Queue es single-threaded (GIL).

**Crítica:** RTL-SDR @ 2.4 MSPS con IQ complex64 = **~20 MB/s** de datos.
- asyncio.Queue podría ser bottleneck
- NumPy operations (FFT, filtering) son CPU-bound

**Alternativa:** ¿Qué tal **multiprocessing.Queue** + worker processes para DSP pesado? O ¿queues de ZeroMQ para IPC?

**3. Dual Storage (HDF5 + FITS)**
❓ **Problema:** Propones HDF5 como primario y FITS como export opcional.

**Crítica:**
- Duplicación de código de escritura
- Conversión HDF5→FITS agrega complejidad
- FITS no es nativo para streams de audio

**Alternativa:** ¿Por qué no **solo HDF5** con metadata astronómica estándar y un script de conversión externo para FITS cuando sea necesario? Reduces complejidad del core.

**4. Error Handling en Pipeline**
❓ **Problema:** Tu skeleton no muestra manejo de errores en plugins.

**Crítica:** Si RFI filter crashea, ¿todo el pipeline se detiene?
- RFI rejection podría fallar con ciertos patrones
- Recording puede fallar por disco lleno
- Multi-SDR correlation puede perder sync

**Alternativa:** ¿Necesitas un **supervisor pattern** que reinicie plugins fallidos sin parar la adquisición?

**5. Taps para Recording**
❓ **Problema:** Dices "usar tee-like en queues" pero no especificas cómo sin copias costosas.

**Crítica:**
- Copiar NumPy arrays grandes (IQ raw) para cada tap es costoso en memoria
- Zero-copy es difícil con Python

**Alternativa:** ¿Shared memory con NumPy? ¿RingBuffers? ¿Qué patrón concreto recomiendas?

**PREGUNTA ABIERTA:**
¿Estoy siendo demasiado conservador o estos son concerns válidos para un sistema real-time? ¿Cómo balanceas simplicidad vs performance en este caso?

Sé crítico con tus propias propuestas. Si tengo razón en algo, admítelo. Si estoy equivocado, explica por qué con datos.`;

        console.log('📤 Enviando debate a Grok...\n');
        console.log('━'.repeat(60));
        console.log(prompt);
        console.log('━'.repeat(60));
        console.log('\n⏳ Esperando respuesta de Grok...\n');

        const result = await adapters.grokAdapter(prompt, {
            maxRetries: 1,
            navigationTimeout: 30000,
            responseTimeout: 180000
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

        console.log('\n💬 Debate completado.');
        console.log('   Presiona Ctrl+C para salir.\n');

        await new Promise(() => {});

    } catch (error) {
        console.error('\n❌ Error:', error.message);
        console.error(error.stack);
    }
}

debateWithGrok().catch(console.error);
