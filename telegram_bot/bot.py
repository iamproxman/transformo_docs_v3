import os
import sys
import asyncio
import logging
import html
import re
import httpx
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters, ContextTypes
)

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger("TransformoDocsBot")

from dotenv import load_dotenv

# Load .env file
load_dotenv(".env")
load_dotenv("../.env")

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000/api/v1")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")


def markdown_to_telegram_html(text: str) -> str:
    """Converts markdown text to Telegram HTML format safely."""
    if not text:
        return ""
    # Escape HTML special chars
    t = html.escape(text)
    # Convert headers ## Header -> <b>Header</b>
    t = re.sub(r'^#{1,6}\s+(.+)$', r'<b>\1</b>', t, flags=re.MULTILINE)
    # Convert bold **text** to <b>text</b>
    t = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', t)
    # Convert italic *text* to <i>text</i>
    t = re.sub(r'\*(.+?)\*', r'<i>\1</i>', t)
    # Convert inline code `text` to <code>text</code>
    t = re.sub(r'`([^`]+)`', r'<code>\1</code>', t)
    # Convert bullet points
    t = re.sub(r'^\s*[\-\*]\s+', '• ', t, flags=re.MULTILINE)
    return t


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sends welcome message and instructions."""
    welcome_text = (
        "✨ <b>Welcome to TransformoDocs Bot!</b> ✨\n\n"
        "I am your Intelligent Document Processing & RAG AI assistant.\n\n"
        "📄 <b>What you can do:</b>\n"
        "• <b>Upload Documents:</b> Send me any PDF, PNG, JPG, or WEBP file directly in this chat!\n"
        "• <b>Auto Field Extraction:</b> I extract key structured fields (amounts, dates, emails, visitor IDs).\n"
        "• <b>Search:</b> Use <code>/search &lt;keyword&gt;</code> to find any document.\n"
        "• <b>RAG Q&A:</b> Ask questions directly or use <code>/ask &lt;question&gt;</code>!\n"
        "• <b>List Docs:</b> View your uploaded library with <code>/list</code>.\n\n"
        "⚡ Send a PDF, image, or ask any question now to get started!"
    )
    await update.message.reply_text(welcome_text, parse_mode="HTML")


async def list_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lists recent documents from backend API."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(f"{API_BASE_URL}/documents")
            if resp.status_code == 200:
                docs = resp.json()
                if not docs:
                    await update.message.reply_text("📂 No documents uploaded yet. Send a file to get started!")
                    return

                msg = f"📂 <b>Your Document Library ({len(docs)} files):</b>\n\n"
                for doc in docs[:15]:
                    status_emoji = "✅" if doc["status"] == "COMPLETED" else "⏳"
                    doc_type = html.escape(doc.get("doc_type") or "DOCUMENT")
                    fn = html.escape(doc["original_filename"])
                    msg += f"{status_emoji} <b>{fn}</b>\n"
                    msg += f"   Type: <code>{doc_type}</code> | Status: <code>{doc['status']}</code>\n\n"
                
                await update.message.reply_text(msg, parse_mode="HTML")
            else:
                await update.message.reply_text("⚠️ Failed to fetch documents from API.")
        except Exception as e:
            await update.message.reply_text(f"⚠️ Connection error: {html.escape(str(e))}")


async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Searches documents via API."""
    query = " ".join(context.args) if context.args else ""
    if not query:
        await update.message.reply_text("Usage: <code>/search &lt;keyword&gt;</code>", parse_mode="HTML")
        return

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(f"{API_BASE_URL}/search", params={"q": query})
            if resp.status_code == 200:
                results = resp.json()
                if not results:
                    await update.message.reply_text(f"🔍 No relevant documents found matching <code>{html.escape(query)}</code>.", parse_mode="HTML")
                    return

                msg = f"🔍 <b>Search results for '{html.escape(query)}' ({len(results)} matches):</b>\n\n"
                for res in results[:5]:
                    fn = html.escape(res['filename'])
                    dt = html.escape(res.get('doc_type','OTHER'))
                    snip = html.escape(res.get('snippet',''))
                    score = int(res.get('score', 0) * 100)
                    msg += f"📄 <b>{fn}</b> (Type: <code>{dt}</code> | Match: {score}%)\n"
                    if snip:
                        msg += f"<i>{snip}</i>\n\n"
                    else:
                        msg += "\n"

                await update.message.reply_text(msg, parse_mode="HTML")
            else:
                await update.message.reply_text("⚠️ Search query failed.")
        except Exception as e:
            await update.message.reply_text(f"⚠️ Error: {html.escape(str(e))}")


async def ask_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """RAG AI Q&A via API (supports /ask command or plain text questions)."""
    question = " ".join(context.args) if (context and context.args) else (update.message.text if update.message else "")
    question = question.strip()
    if not question:
        await update.message.reply_text("Usage: <code>/ask &lt;your question&gt;</code> or type your question directly.", parse_mode="HTML")
        return

    status_msg = await update.message.reply_text("🧠 <i>TransformoDocs AI is analyzing your documents...</i>", parse_mode="HTML")

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.post(f"{API_BASE_URL}/search/ask", json={"question": question})
            if resp.status_code == 200:
                data = resp.json()
                raw_answer = data.get("answer", "No answer found.")
                sources = data.get("sources", [])

                formatted_answer = markdown_to_telegram_html(raw_answer)

                sources_str = ""
                if sources:
                    sources_str = "\n\n📌 <b>Sources Referenced (" + str(len(sources)) + "):</b>\n"
                    for s in sources:
                        fn = html.escape(s.get("filename", "Document"))
                        sources_str += f"• <code>{fn}</code>\n"

                reply = f"🤖 <b>RAG AI Answer:</b>\n\n{formatted_answer}{sources_str}"
                await status_msg.edit_text(reply, parse_mode="HTML")
            else:
                await status_msg.edit_text("⚠️ RAG Q&A query failed.")
        except Exception as e:
            await status_msg.edit_text(f"⚠️ Error: {html.escape(str(e))}")


async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Routes any plain text message to RAG AI Q&A automatically."""
    if update.message and update.message.text:
        await ask_command(update, context)


async def handle_document_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles PDF and Image document uploads in Telegram chat."""
    message = update.message
    file_obj = None
    filename = "document"

    if message.document:
        file_obj = await message.document.get_file()
        filename = message.document.file_name or "document.pdf"
    elif message.photo:
        file_obj = await message.photo[-1].get_file()
        filename = "scanned_photo.jpg"
    else:
        return

    progress_msg = await message.reply_text(f"📥 <b>Receiving '{html.escape(filename)}'...</b>", parse_mode="HTML")

    # Download file bytes
    file_bytes = await file_obj.download_as_bytearray()

    await progress_msg.edit_text("⚡ <b>Processing OCR & AI field extraction...</b>", parse_mode="HTML")

    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            files = {"file": (filename, bytes(file_bytes))}
            resp = await client.post(f"{API_BASE_URL}/documents/upload", files=files)
            if resp.status_code in [200, 202]:
                doc_data = resp.json()

                # If upload returned list, take first
                if isinstance(doc_data, list) and doc_data:
                    doc_data = doc_data[0]

                doc_id = doc_data["id"]

                # Wait for status completion (poll up to 10s)
                for _ in range(10):
                    await asyncio.sleep(1.0)
                    doc_resp = await client.get(f"{API_BASE_URL}/documents/{doc_id}")
                    if doc_resp.status_code == 200:
                        doc_info = doc_resp.json()
                        if doc_info["status"] in ["COMPLETED", "FAILED"]:
                            doc_data = doc_info
                            break

                status = doc_data.get("status", "COMPLETED")
                doc_type = html.escape(doc_data.get("doc_type", "DOCUMENT"))
                extracted = doc_data.get("extracted_fields", [])

                reply = f"✅ <b>Document Ingested Successfully!</b>\n\n"
                reply += f"📄 <b>File:</b> <code>{html.escape(filename)}</code>\n"
                reply += f"🏷️ <b>Type:</b> <code>{doc_type}</code> | Status: <code>{status}</code>\n\n"

                if extracted:
                    reply += "📋 <b>Extracted Fields:</b>\n"
                    for f in extracted:
                        val = f.get("value_text") or f.get("value_number") or f.get("value_date")
                        if val:
                            lbl = html.escape(str(f.get('field_label') or f.get('field_key')))
                            reply += f"• <b>{lbl}:</b> <code>{html.escape(str(val))}</code>\n"
                else:
                    reply += "Text indexed and searchable via <code>/search</code> or by asking any question!"

                await progress_msg.edit_text(reply, parse_mode="HTML")
            else:
                await progress_msg.edit_text(f"❌ Upload failed with status code {resp.status_code}.")
        except Exception as e:
            await progress_msg.edit_text(f"❌ Error uploading file: {html.escape(str(e))}")


def main():
    if not TELEGRAM_BOT_TOKEN:
        print("Notice: TELEGRAM_BOT_TOKEN is not set. Telegram bot will start when token is provided in .env!")
        return

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", start_command))
    app.add_handler(CommandHandler("list", list_command))
    app.add_handler(CommandHandler("search", search_command))
    app.add_handler(CommandHandler("ask", ask_command))
    app.add_handler(MessageHandler(filters.Document.ALL | filters.PHOTO, handle_document_upload))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))

    print("Starting TransformoDocs Telegram Bot...")
    app.run_polling()


if __name__ == "__main__":
    main()
