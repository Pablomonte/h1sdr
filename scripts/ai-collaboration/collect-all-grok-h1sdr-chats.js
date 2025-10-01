#!/usr/bin/env node

/**
 * Colecta todos los chats de Grok relacionados con H1SDR
 */

require('dotenv').config();
const { chromium } = require('playwright');
const fs = require('fs').promises;

async function collectAllH1SDRChats() {
    console.log('📚 Colectando todos los chats de H1SDR de Grok...\n');

    let browser;

    try {
        browser = await chromium.connectOverCDP('http://localhost:9222');
        console.log('✅ Conectado a navegador\n');

        const contexts = browser.contexts();
        const page = contexts[0].pages()[0];

        // Navegar a Grok home si no estamos ahí
        console.log('📍 Navegando a Grok...');
        if (!page.url().includes('grok.com')) {
            await page.goto('https://grok.com', { waitUntil: 'load', timeout: 30000 });
        }
        await page.waitForTimeout(2000);

        console.log('🔍 Buscando historial de conversaciones...\n');

        // Extraer todos los títulos de conversaciones del sidebar
        const conversationList = await page.evaluate(() => {
            const conversations = [];

            // Buscar todos los elementos que parecen títulos de conversaciones
            // En Grok, están en el sidebar con diferentes selectores posibles
            const selectors = [
                'a[href^="/c/"]',  // Links a conversaciones
                '[data-testid*="conversation"]',  // Elementos con testid
                '.conversation-item',  // Clase específica
                'nav a',  // Links en navegación
            ];

            const foundElements = new Set();

            selectors.forEach(selector => {
                try {
                    const elements = document.querySelectorAll(selector);
                    elements.forEach(el => {
                        const href = el.getAttribute('href');
                        const text = el.textContent?.trim();

                        if (href && href.includes('/c/') && text && text.length > 0) {
                            const conversationId = href.match(/\/c\/([^\/]+)/)?.[1];
                            if (conversationId) {
                                foundElements.add(JSON.stringify({
                                    id: conversationId,
                                    title: text,
                                    url: `https://grok.com${href}`
                                }));
                            }
                        }
                    });
                } catch (e) {
                    console.error(`Error con selector ${selector}:`, e.message);
                }
            });

            return Array.from(foundElements).map(item => JSON.parse(item));
        });

        console.log(`📊 Conversaciones encontradas: ${conversationList.length}\n`);

        // Filtrar conversaciones relacionadas con H1SDR
        const h1sdrChats = conversationList.filter(conv =>
            conv.title.toLowerCase().includes('h1sdr') ||
            conv.title.toLowerCase().includes('radioastronomía') ||
            conv.title.toLowerCase().includes('websdr') ||
            conv.title.toLowerCase().includes('arquitectura') ||
            conv.title.toLowerCase().includes('crítica')
        );

        console.log(`🎯 Chats relacionados con H1SDR: ${h1sdrChats.length}\n`);

        h1sdrChats.forEach((chat, index) => {
            console.log(`  ${index + 1}. ${chat.title}`);
            console.log(`     ID: ${chat.id}`);
            console.log();
        });

        // Extraer contenido de cada chat
        const allChatsContent = [];

        for (const [index, chat] of h1sdrChats.entries()) {
            console.log(`📖 Extrayendo chat ${index + 1}/${h1sdrChats.length}: ${chat.title}...`);

            try {
                // Navegar al chat
                await page.goto(chat.url, { waitUntil: 'load', timeout: 30000 });
                await page.waitForTimeout(3000);

                // Extraer todo el texto del chat
                const chatContent = await page.evaluate(() => {
                    return document.body.innerText;
                });

                allChatsContent.push({
                    title: chat.title,
                    id: chat.id,
                    url: chat.url,
                    content: chatContent
                });

                console.log(`  ✅ Extraído: ${chatContent.length} caracteres\n`);

            } catch (error) {
                console.log(`  ❌ Error extrayendo chat: ${error.message}\n`);
            }
        }

        // Guardar todo en un archivo consolidado
        console.log('💾 Guardando contenido consolidado...\n');

        let consolidatedContent = `# 📚 Todos los Chats de H1SDR con Grok\n\n`;
        consolidatedContent += `**Fecha de extracción:** ${new Date().toISOString()}\n`;
        consolidatedContent += `**Total de chats:** ${allChatsContent.length}\n\n`;
        consolidatedContent += '═'.repeat(60) + '\n\n';

        allChatsContent.forEach((chat, index) => {
            consolidatedContent += `## Chat ${index + 1}: ${chat.title}\n\n`;
            consolidatedContent += `**ID:** ${chat.id}\n`;
            consolidatedContent += `**URL:** ${chat.url}\n\n`;
            consolidatedContent += '─'.repeat(60) + '\n\n';
            consolidatedContent += chat.content + '\n\n';
            consolidatedContent += '═'.repeat(60) + '\n\n';
        });

        await fs.writeFile('all-h1sdr-grok-chats.md', consolidatedContent);
        console.log('✅ Contenido guardado en: all-h1sdr-grok-chats.md\n');

        // También guardar un índice JSON
        const index = allChatsContent.map(chat => ({
            title: chat.title,
            id: chat.id,
            url: chat.url,
            length: chat.content.length
        }));

        await fs.writeFile('h1sdr-chats-index.json', JSON.stringify(index, null, 2));
        console.log('✅ Índice guardado en: h1sdr-chats-index.json\n');

        // Resumen
        console.log('═'.repeat(60));
        console.log('📊 RESUMEN:');
        console.log('═'.repeat(60));
        console.log(`Total de conversaciones en Grok: ${conversationList.length}`);
        console.log(`Chats relacionados con H1SDR: ${h1sdrChats.length}`);
        console.log(`Chats extraídos exitosamente: ${allChatsContent.length}`);
        console.log(`Tamaño total: ${consolidatedContent.length.toLocaleString()} caracteres`);
        console.log('═'.repeat(60));

    } catch (error) {
        console.error('\n❌ Error:', error.message);
        console.error(error.stack);
    } finally {
        if (browser) {
            await browser.close();
        }
    }
}

collectAllH1SDRChats().catch(console.error);
