import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime

# Conectar ao banco
conn = sqlite3.connect("estoque.db", check_same_thread=False)
cursor = conn.cursor()

# Criar tabela de produtos com campo de alerta
cursor.execute(
    """
CREATE TABLE IF NOT EXISTS produtos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT UNIQUE NOT NULL,
    descricao TEXT,
    fornecedor TEXT,
    data_cadastro TEXT NOT NULL,
    alerta INTEGER DEFAULT 0
)
"""
)

# Tabela de movimentações
cursor.execute(
    """
CREATE TABLE IF NOT EXISTS movimentacoes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    produto_id INTEGER NOT NULL,
    tipo TEXT NOT NULL,
    quantidade INTEGER NOT NULL,
    data TEXT NOT NULL,
    FOREIGN KEY (produto_id) REFERENCES produtos(id)
)
"""
)
conn.commit()


# Funções utilitárias
def get_datetime():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def cadastrar_produto(nome, descricao, fornecedor, alerta):
    data = get_datetime()
    try:
        cursor.execute(
            """
            INSERT INTO produtos (nome, descricao, fornecedor, data_cadastro, alerta)
            VALUES (?, ?, ?, ?, ?)
        """,
            (nome, descricao, fornecedor, data, alerta),
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False


def excluir_produto(nome):
    produto_id = buscar_produto_id(nome)
    if not produto_id:
        return "Produto não encontrado."

    # Excluir movimentações primeiro (por integridade referencial)
    cursor.execute("DELETE FROM movimentacoes WHERE produto_id = ?", (produto_id,))
    cursor.execute("DELETE FROM produtos WHERE id = ?", (produto_id,))
    conn.commit()
    return True


def buscar_produto_id(nome):
    cursor.execute("SELECT id FROM produtos WHERE nome = ?", (nome,))
    result = cursor.fetchone()
    return result[0] if result else None


def registrar_movimentacao(nome, tipo, quantidade):
    produto_id = buscar_produto_id(nome)
    if not produto_id:
        return "Produto não cadastrado."

    if tipo == "saida":
        estoque = consultar_estoque(nome)
        if estoque is None or estoque < quantidade:
            return "Estoque insuficiente."

    data = get_datetime()
    cursor.execute(
        """
        INSERT INTO movimentacoes (produto_id, tipo, quantidade, data)
        VALUES (?, ?, ?, ?)
    """,
        (produto_id, tipo, quantidade, data),
    )
    conn.commit()
    return True


def consultar_estoque(nome):
    produto_id = buscar_produto_id(nome)
    if not produto_id:
        return None
    cursor.execute(
        """
        SELECT 
            SUM(CASE WHEN tipo = 'entrada' THEN quantidade ELSE -quantidade END)
        FROM movimentacoes
        WHERE produto_id = ?
    """,
        (produto_id,),
    )
    result = cursor.fetchone()
    return result[0] if result and result[0] is not None else 0


def listar_estoque_completo():
    cursor.execute(
        """
        SELECT p.nome AS produto,
               p.descricao,
               p.fornecedor,
               p.data_cadastro,
               p.alerta,
               COALESCE(SUM(CASE WHEN m.tipo = 'entrada' THEN m.quantidade ELSE -m.quantidade END), 0) AS quantidade
        FROM produtos p
        LEFT JOIN movimentacoes m ON p.id = m.produto_id
        GROUP BY p.id
    """
    )
    return pd.DataFrame(
        cursor.fetchall(),
        columns=[
            "Produto",
            "Descrição",
            "Fornecedor",
            "Data Cadastro",
            "Alerta",
            "Estoque Atual",
        ],
    )


def listar_movimentacoes(tipo):
    cursor.execute(
        """
        SELECT m.id, p.nome, m.quantidade, m.data
        FROM movimentacoes m
        JOIN produtos p ON m.produto_id = p.id
        WHERE m.tipo = ?
        ORDER BY m.data DESC
    """,
        (tipo,),
    )
    return pd.DataFrame(
        cursor.fetchall(), columns=["ID", "Produto", "Quantidade", "Data/Hora"]
    )


def listar_nomes_produtos():
    cursor.execute("SELECT nome FROM produtos ORDER BY nome")
    return [row[0] for row in cursor.fetchall()]


# Interface Streamlit
st.set_page_config(page_title="Controle de Estoque - 216 AT", layout="wide")
st.title("📦 Sistema de Controle de Estoque - FILIAL 216 AT")

menu = st.sidebar.radio(
    "Menu",
    ["Cadastrar Produto", "Entrada", "Saída", "Consultar Estoque", "Excluir Produto"],
)


# CADASTRO DE PRODUTOS
if menu == "Cadastrar Produto":
    st.subheader("📋 Cadastro e Edição de Produto")

    aba = st.radio("Escolha a ação:", ["Cadastrar Novo", "Editar Existente"])

    if aba == "Cadastrar Novo":
        with st.form(key="form_cadastro", clear_on_submit=True):
            nome = st.text_input("Nome do produto").strip()
            descricao = st.text_area("Descrição do produto")
            fornecedor = st.text_input("Fornecedor")
            alerta = st.number_input("Quantidade mínima de alerta", min_value=0, step=1)
            submit = st.form_submit_button("Cadastrar")

            if submit:
                if nome.strip() and fornecedor.strip():
                    sucesso = cadastrar_produto(
                        nome, descricao or "", fornecedor, alerta
                    )
                    if sucesso:
                        st.success(f"✅ Produto '{nome}' cadastrado com sucesso!")
                    else:
                        st.warning("⚠️ Produto já cadastrado.")
                else:
                    st.error("❌ Preencha todos os campos obrigatórios.")

    elif aba == "Editar Existente":
        nomes = listar_nomes_produtos()
        if nomes:
            produto_selecionado = st.selectbox("Selecione o produto para editar", nomes)

            cursor.execute(
                "SELECT descricao, fornecedor, alerta FROM produtos WHERE nome = ?",
                (produto_selecionado,),
            )
            dados = cursor.fetchone()
            descricao_atual = dados[0] if dados else ""
            fornecedor_atual = dados[1] if dados else ""
            alerta_atual = dados[2] if dados else 0

            with st.form(key="form_edicao", clear_on_submit=True):
                novo_nome = st.text_input(
                    "Novo nome do produto", value=produto_selecionado
                )
                nova_descricao = st.text_area("Nova descrição", value=descricao_atual)
                novo_fornecedor = st.text_input(
                    "Novo fornecedor", value=fornecedor_atual
                )
                novo_alerta = st.number_input(
                    "Nova quantidade mínima de alerta",
                    min_value=0,
                    step=1,
                    value=alerta_atual,
                )
                salvar = st.form_submit_button("Salvar Alterações")

                if salvar:
                    try:
                        cursor.execute(
                            """
                            UPDATE produtos 
                            SET nome = ?, descricao = ?, fornecedor = ?, alerta = ?
                            WHERE nome = ?
                        """,
                            (
                                novo_nome.strip(),
                                nova_descricao,
                                novo_fornecedor,
                                novo_alerta,
                                produto_selecionado,
                            ),
                        )
                        conn.commit()
                        st.success("✅ Produto atualizado com sucesso!")
                    except sqlite3.IntegrityError:
                        st.error("❌ Já existe um produto com esse nome.")
        else:
            st.info("ℹ️ Nenhum produto cadastrado ainda.")

# EXCLUSÃO DE PRODUTOS
elif menu == "Excluir Produto":
    st.subheader("🗑️ Excluir Produto Cadastrado")

    nomes_produtos = listar_nomes_produtos()

    if nomes_produtos:
        produto = st.selectbox("Selecione o produto para excluir", nomes_produtos)
        confirmar = st.checkbox(f"Confirmar exclusão do produto '{produto}'")

        if confirmar:
            if st.button("Excluir Produto"):
                resultado = excluir_produto(produto)
                if resultado is True:
                    st.success(f"✅ Produto '{produto}' excluído com sucesso!")
                else:
                    st.error(f"❌ Erro: {resultado}")
    else:
        st.info("ℹ️ Nenhum produto cadastrado.")


# ENTRADA DE PRODUTOS
elif menu == "Entrada":
    st.subheader("📥 Entrada de Mercadoria")

    nomes_produtos = listar_nomes_produtos()

    if nomes_produtos:
        with st.form(key="form_entrada", clear_on_submit=True):
            produto = st.selectbox("Produto", nomes_produtos)
            quantidade = st.number_input("Quantidade", min_value=1, step=1)
            submit = st.form_submit_button("Registrar Entrada")

            if submit:
                resultado = registrar_movimentacao(produto, "entrada", quantidade)
                if resultado is True:
                    st.success("✅ Entrada registrada com sucesso!")
                else:
                    st.error(f"❌ Erro: {resultado}")

        st.markdown("---")
        st.markdown("### 📄 Histórico de Entradas")
        df_entrada = listar_movimentacoes("entrada")
        st.dataframe(df_entrada, use_container_width=True)
    else:
        st.info("ℹ️ Nenhum produto cadastrado.")

# SAÍDA DE PRODUTOS
elif menu == "Saída":
    st.subheader("📤 Saída de Mercadoria")

    nomes_produtos = listar_nomes_produtos()

    if nomes_produtos:
        with st.form(key="form_saida", clear_on_submit=True):
            produto = st.selectbox("Produto", nomes_produtos)
            quantidade = st.number_input("Quantidade", min_value=1, step=1)
            submit = st.form_submit_button("Registrar Saída")

            if submit:
                resultado = registrar_movimentacao(produto, "saida", quantidade)
                if resultado is True:
                    st.success("✅ Saída registrada com sucesso!")
                else:
                    st.error(f"❌ Erro: {resultado}")

        st.markdown("---")
        st.markdown("### 📄 Histórico de Saídas")
        df_saida = listar_movimentacoes("saida")
        st.dataframe(df_saida, use_container_width=True)
    else:
        st.info("ℹ️ Nenhum produto cadastrado.")

# CONSULTA DE ESTOQUE
elif menu == "Consultar Estoque":
    st.subheader("📦 Estoque Atual")
    df = listar_estoque_completo()
    if not df.empty:
        # Calcular o status com base no estoque atual e alerta
        def calcular_status(row):
            if row["Estoque Atual"] > row["Alerta"]:
                return "Estoque Completo"
            elif row["Estoque Atual"] > 0:
                return "Estoque Regular"
            else:
                return "Estoque Vazio"

        df["Status"] = df.apply(calcular_status, axis=1)

        # Aplicar cores ao status
        def cor_status(val):
            if val == "Estoque Completo":
                return "background-color: #b5e48c; font-weight: bold"
            elif val == "Estoque Regular":
                return "background-color: #ffc300; font-weight: bold"
            elif val == "Estoque Vazio":
                return "background-color: #ff6392; font-weight: bold"
            return ""

        st.dataframe(
            df.style.applymap(cor_status, subset=["Status"]), use_container_width=True
        )
    else:
        st.info("ℹ️ Nenhum produto cadastrado.")

# Rodapé fixo na sidebar
st.markdown(
    """
    <style>
    [data-testid="stSidebar"]::after {
        content: "***\\A- DAYVISSON TENORIO -\\A desenvolvedor responsável\\A ***";
        white-space: pre-line;
        position: absolute;
        bottom: 20px;
        left: 0;
        width: 100%;
        text-align: center;
        font-size: 16px;
        color: gray;
        opacity: 0.8;
    }
    </style>
    """,
    unsafe_allow_html=True,
)
