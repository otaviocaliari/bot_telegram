import os
import sqlite3
from datetime import datetime, timedelta
import config_metas

DB_PATH = os.path.join(os.environ.get('DATA_PATH', '/data'), 'controle_financeiro.db')

def conectar():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def inicializar_banco():
    conn = conectar()
    # Adicionada a coluna 'status' (ativo/arquivado)
    conn.execute('''CREATE TABLE IF NOT EXISTS gastos
                    (id INTEGER PRIMARY KEY, valor REAL, descricao TEXT,
                     grupo TEXT, tipo TEXT, data_hora TEXT, status TEXT DEFAULT 'ativo')''')
    conn.commit()
    conn.close()

def registrar_gasto(valor, descricao, grupo, tipo):
    agora = datetime.utcnow() + timedelta(hours=-3)
    data_hora = agora.strftime("%d/%m/%Y %H:%M")
    conn = conectar()
    conn.execute('INSERT INTO gastos (valor, descricao, grupo, tipo, data_hora, status) VALUES (?, ?, ?, ?, ?, ?)',
                 (valor, descricao, grupo, tipo, data_hora, 'ativo'))
    conn.commit()
    conn.close()
    return data_hora

def obter_meta(categoria="Geral"):
    return config_metas.METAS.get(categoria, 0.0)

def obter_total_variavel():
    conn = conectar()
    # Soma apenas os ATIVOS
    cursor = conn.execute("SELECT SUM(valor) FROM gastos WHERE grupo = 'variavel' AND status = 'ativo'")
    total = cursor.fetchone()[0]
    conn.close()
    return total if total else 0.0

def obter_resumo_por_grupo(grupo):
    conn = conectar()
    # Soma apenas os ATIVOS agrupados
    cursor = conn.execute("SELECT tipo, SUM(valor) FROM gastos WHERE grupo = ? AND status = 'ativo' GROUP BY tipo", (grupo,))
    resumo = cursor.fetchall()
    conn.close()
    return resumo

def obter_detalhes_ativos():
    conn = conectar()
    cursor = conn.execute(
        "SELECT id, data_hora, grupo, tipo, descricao, valor FROM gastos WHERE status = 'ativo' ORDER BY id DESC"
    )
    dados = cursor.fetchall()
    conn.close()
    return dados

def zerar_gastos_variaveis():
    conn = conectar()
    # Em vez de DELETE, fazemos UPDATE para 'arquivado'
    conn.execute("UPDATE gastos SET status = 'arquivado' WHERE grupo = 'variavel' AND status = 'ativo'")
    conn.commit()
    conn.close()

def zerar_gastos_fixos():
    conn = conectar()
    conn.execute("UPDATE gastos SET status = 'arquivado' WHERE grupo = 'fixo' AND status = 'ativo'")
    conn.commit()
    conn.close()

def reset_total():
    conn = conectar()
    conn.execute("DROP TABLE IF EXISTS gastos")
    conn.commit()
    conn.close()
    inicializar_banco()

def obter_gasto_por_id(id_gasto):
    conn = conectar()
    cursor = conn.execute(
        "SELECT id, data_hora, grupo, tipo, descricao, valor FROM gastos WHERE id = ?",
        (id_gasto,)
    )
    resultado = cursor.fetchone()
    conn.close()
    return resultado

def apagar_gasto(id_gasto):
    conn = conectar()
    conn.execute("DELETE FROM gastos WHERE id = ?", (id_gasto,))
    conn.commit()
    conn.close()