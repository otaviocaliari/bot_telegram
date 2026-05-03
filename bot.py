import os
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import database as db
import config_metas

TOKEN = os.environ['TOKEN']
bot = telebot.TeleBot(TOKEN)

# Inicializa o banco (garante a coluna 'status')
db.inicializar_banco()

# --- COMANDOS INICIAIS ---

@bot.message_handler(commands=['start', 'ajuda'])
def enviar_boas_vindas(mensagem):
    texto = (
        "💰 **Controle Financeiro Familiar**\n\n"
        "🛍️ /gastar <valor> <item> - Registo Semanal\n"
        "🏢 /fixo - Menu de categorias Mensais\n"
        "📊 /resumo - Saldo e metas atuais\n"
        "📝 /detalhes - Lista de gastos ativos\n"
        "🧹 /zerar - Arquiva gastos (limpa o saldo)\n"
        "⚠️ /reset_teste - Apaga TUDO permanentemente"
        "🗑️ /apagar - Remove uma entrada incorreta\n"
    )
    bot.reply_to(mensagem, texto, parse_mode='Markdown')

# --- COMANDO /DETALHES ---

@bot.message_handler(commands=['detalhes'])
def enviar_detalhes(mensagem):
    gastos = db.obter_detalhes_ativos()
    if not gastos:
        bot.reply_to(mensagem, "Não há gastos ativos no momento.")
        return

    relatorio = "📝 **DETALHAMENTO DE GASTOS ATIVOS**\n\n"
    for _, data, grupo, tipo, desc, valor in gastos:
        origem = tipo.replace('_', ' ') if grupo == 'fixo' else 'Variável'
        relatorio += f"📅 {data}\n🔹 {origem}: {desc}\n💰 *R$ {valor:.2f}*\n"
        relatorio += "--------------------------\n"

    # Prevenção contra limite de caracteres do Telegram
    if len(relatorio) > 4000:
        bot.send_message(mensagem.chat.id, relatorio[:4000], parse_mode='Markdown')
        bot.send_message(mensagem.chat.id, "... (relatório muito longo)", parse_mode='Markdown')
    else:
        bot.send_message(mensagem.chat.id, relatorio, parse_mode='Markdown')

# --- COMANDO /RESUMO ---

@bot.message_handler(commands=['resumo'])
def mostrar_resumo(mensagem):
    meta_geral = db.obter_meta("Geral")
    total_var = db.obter_total_variavel()
    saldo_semanal = meta_geral - total_var

    texto = f"📊 **RESUMO FINANCEIRO**\n\n"
    texto += f"🗓 **SEMANAL (Geral)**\n"
    texto += f"🎯 Meta: R$ {meta_geral:.2f}\n"
    texto += f"💸 Gasto: R$ {total_var:.2f}\n"
    texto += f"💰 Saldo: R$ {saldo_semanal:.2f}\n"
    texto += f"{'✅ Dentro da Meta' if saldo_semanal >= 0 else '⚠️ Orçamento Estourado'}\n\n"

    texto += f"📅 **MENSAL (Fixos)**\n"
    resumo_fixo = db.obter_resumo_por_grupo('fixo')

    if not resumo_fixo:
        texto += "_Nenhum gasto fixo registado._"
    else:
        for tipo, total in resumo_fixo:
            meta_tipo = db.obter_meta(tipo)
            texto += f"🔹 *{tipo.replace('_', ' ')}*: R$ {total:.2f}"
            if meta_tipo > 0:
                resta = meta_tipo - total
                texto += f"\n   (Meta: R$ {meta_tipo:.2f} | Resta: R$ {resta:.2f})"
            texto += "\n"

    bot.send_message(mensagem.chat.id, texto, parse_mode='Markdown')

# --- COMANDO /GASTAR (Variável) ---

@bot.message_handler(commands=['gastar'])
def registrar_gasto_variavel(mensagem):
    try:
        partes = mensagem.text.split(' ', 2)
        valor = float(partes[1].replace(',', '.'))
        desc = partes[2] if len(partes) > 2 else "Outros"

        db.registrar_gasto(valor, desc, 'variavel', '')
        bot.reply_to(mensagem, f"✅ Variável: R$ {valor:.2f} ({desc}) registado!")
    except:
        bot.reply_to(mensagem, "❌ Use: /gastar 50.00 mercado")

# --- COMANDO /FIXO ---

@bot.message_handler(commands=['fixo'])
def menu_fixo(mensagem):
    markup = InlineKeyboardMarkup(row_width=2)
    categorias = ["Almoço_Presencial", "Pets", "Combustível", "Farmácia", "Mercado", "Outros"]
    botoes = [InlineKeyboardButton(c.replace('_', ' '), callback_data=f"fixo_{c}") for c in categorias]
    markup.add(*botoes)
    bot.send_message(mensagem.chat.id, "👇 Escolha a categoria do gasto fixo:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('fixo_'))
def clique_fixo(call):
    tipo = call.data.replace('fixo_', '')
    msg = bot.send_message(call.message.chat.id, f"📂 Categoria: *{tipo.replace('_', ' ')}*\nDigite o **valor** e a **descrição**:", parse_mode="Markdown")
    bot.register_next_step_handler(msg, lambda m: salvar_fixo(m, tipo))

def salvar_fixo(mensagem, tipo):
    try:
        partes = mensagem.text.split(' ', 1)
        valor = float(partes[0].replace(',', '.'))
        desc = partes[1] if len(partes) > 1 else "Fixo"
        db.registrar_gasto(valor, desc, 'fixo', tipo)
        bot.reply_to(mensagem, f"✅ Fixo: R$ {valor:.2f} salvo em {tipo.replace('_', ' ')}!")
    except:
        bot.reply_to(mensagem, "❌ Erro! Exemplo: 100 farmacia")

# --- COMANDO /ZERAR (Arquivamento) ---

@bot.message_handler(commands=['zerar'])
def menu_zerar(mensagem):
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("Arquivar Semana", callback_data="z_v"),
               InlineKeyboardButton("Arquivar Mês", callback_data="z_f"))
    bot.send_message(mensagem.chat.id, "🧹 **Zerar Saldo?**\nIsso moverá os gastos atuais para o arquivo, mas manterá o histórico na base de dados.", reply_markup=markup, parse_mode='Markdown')

@bot.callback_query_handler(func=lambda call: call.data.startswith('z_'))
def processa_zeragem(call):
    if call.data == "z_v":
        db.zerar_gastos_variaveis()
        tipo = "Semanais"
    else:
        db.zerar_gastos_fixos()
        tipo = "Fixos"
    bot.edit_message_text(f"✅ Gastos {tipo} arquivados! Saldo reiniciado.", call.message.chat.id, call.message.message_id)

# --- COMANDO /RESET_TESTE (Apagar Tudo) ---

@bot.message_handler(commands=['reset_teste'])
def reset_geral(mensagem):
    db.reset_total()
    bot.reply_to(mensagem, "🚨 **LIMPEZA TOTAL!** O banco de dados foi recriado e o histórico apagado.")

# --- COMANDO /APAGAR ---

@bot.message_handler(commands=['apagar'])
def menu_apagar(mensagem):
    gastos = db.obter_detalhes_ativos()
    if not gastos:
        bot.reply_to(mensagem, "Não há gastos ativos para apagar.")
        return

    markup = InlineKeyboardMarkup(row_width=1)
    for id_gasto, data, grupo, tipo, desc, valor in gastos:
        origem = tipo.replace('_', ' ') if grupo == 'fixo' else 'Variável'
        label = f"{data} | {origem} | {desc} | R$ {valor:.2f}"
        markup.add(InlineKeyboardButton(label, callback_data=f"del_{id_gasto}"))

    bot.send_message(mensagem.chat.id, "🗑️ Selecione o gasto que deseja apagar:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('del_'))
def confirmar_apagar(call):
    # Evita conflito com outros callbacks que começam com 'del_'
    if call.data == 'del_cancel':
        return

    id_gasto = int(call.data.replace('del_', ''))
    gasto = db.obter_gasto_por_id(id_gasto)

    if not gasto:
        bot.edit_message_text("❌ Gasto não encontrado.", call.message.chat.id, call.message.message_id)
        return

    id_gasto, data, grupo, tipo, desc, valor = gasto
    origem = tipo.replace('_', ' ') if grupo == 'fixo' else 'Variável'

    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("✅ Confirmar", callback_data=f"delok_{id_gasto}"),
        InlineKeyboardButton("❌ Cancelar", callback_data="del_cancel")
    )

    bot.edit_message_text(
        f"⚠️ Confirma a exclusão?\n\n📅 {data}\n🔹 {origem}: {desc}\n💰 R$ {valor:.2f}",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith('delok_'))
def executar_apagar(call):
    id_gasto = int(call.data.replace('delok_', ''))
    db.apagar_gasto(id_gasto)
    bot.edit_message_text("✅ Gasto apagado com sucesso!", call.message.chat.id, call.message.message_id)

@bot.callback_query_handler(func=lambda call: call.data == 'del_cancel')
def cancelar_apagar(call):
    bot.edit_message_text("❌ Exclusão cancelada.", call.message.chat.id, call.message.message_id)

if __name__ == "__main__":
    print("🚀 Bot Financeiro Ativo...")
    bot.infinity_polling(timeout=60, long_polling_timeout=30)