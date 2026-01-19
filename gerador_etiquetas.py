import tkinter as tk
from tkinter import filedialog, messagebox, ttk, simpledialog
from PIL import Image, ImageTk
import pandas as pd
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor
import os
import json
import logging
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime
import io
# Tenta importar pdf2image, se não der, segue sem preview
try:
    from pdf2image import convert_from_bytes
    HAS_PDF2IMAGE = True
except ImportError:
    HAS_PDF2IMAGE = False

# === CONFIGURAÇÃO DE LOGGING ===
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler('app.log'), logging.StreamHandler()]
)
logger = logging.getLogger("FortunneApp")

# === CONSTANTES & CONFIGURAÇÃO ===
@dataclass
class EtiquetaConfig:
    """Configuração para etiquetas A6 (105x148.5mm) em folha A4"""
    LARGURA: float = 105 * mm
    ALTURA: float = 148.5 * mm
    MARGEM: float = 5 * mm
    
    # Fontes
    FONTE_TITULO: int = 13
    FONTE_SUBTITULO: int = 9
    FONTE_SPECS: int = 7
    FONTE_TAMANHOS: int = 7
    
    # Cores
    COR_FUNDO: HexColor = HexColor('#FFFFFF')
    COR_TEXTO: HexColor = HexColor('#000000')
    
    # Boxes do meio
    BOX_LARGURA: float = 47 * mm
    BOX_ALTURA: float = 56 * mm
    BOX_Y_BASE: float = 45 * mm
    
    # Rodapé
    BOX_RODAPE_ALTURA: float = 28 * mm
    BOX_RODAPE_Y: float = 12 * mm
    
    # Imagem
    TITULO_Y_OFFSET: float = 12 * mm
    IMG_MARGEM_TOPO: float = 3 * mm
    IMG_MARGEM_BASE: float = 5 * mm
    IMG_LARGURA_MAX: float = 85 * mm

# Configuração padrão
DEFAULT_CONFIG = {
    "Sofá": {
        "campos": ["Módulos", "Braços", "Almofadas", "Tecido", "Pé"],
        "placeholders": {"Módulos": "3 Módulos", "Braços": "25cm", "Tecido": "Linho"}
    },
    "Mesa": {
        "campos": ["Material", "Acabamento", "Formato", "Tampo", "Base"],
        "placeholders": {"Material": "Madeira", "Formato": "Retangular"}
    },
    "Cadeira": {
        "campos": ["Material", "Estofado", "Estrutura", "Acabamento"],
        "placeholders": {"Material": "Madeira", "Estofado": "Tecido"}
    }
}

# === GERENCIADOR DE ARQUIVOS E DADOS ===
class GerenciadorDados:
    ARQUIVO_CONFIG = 'produtos.json'
    ARQUIVO_HISTORICO = 'historico.json'
    ARQUIVO_LAYOUTS = 'layouts_salvos.json'
    ARQUIVO_DB_PRODUTOS = 'db_produtos.json'

    @classmethod
    def carregar_config(cls) -> Dict:
        """Carrega configurações de tipos de produtos"""
        if not os.path.exists(cls.ARQUIVO_CONFIG):
            cls.salvar_config(DEFAULT_CONFIG)
            return DEFAULT_CONFIG
        try:
            with open(cls.ARQUIVO_CONFIG, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Config corrompida: {e}")
            return DEFAULT_CONFIG

    @classmethod
    def salvar_config(cls, dados: Dict):
        with open(cls.ARQUIVO_CONFIG, 'w', encoding='utf-8') as f:
            json.dump(dados, f, indent=4, ensure_ascii=False)

    @classmethod
    def carregar_historico(cls) -> Dict:
        if not os.path.exists(cls.ARQUIVO_HISTORICO): return {}
        try:
            with open(cls.ARQUIVO_HISTORICO, 'r', encoding='utf-8') as f:
                return json.load(f)
        except: return {}

    @classmethod
    def salvar_historico(cls, novo_dado: Dict):
        hist = cls.carregar_historico()
        for k, v in novo_dado.items():
            if v and isinstance(v, str) and v.strip():
                if k not in hist: hist[k] = []
                if v not in hist[k]: 
                    hist[k].append(v)
                    hist[k] = hist[k][-15:]
        with open(cls.ARQUIVO_HISTORICO, 'w', encoding='utf-8') as f:
            json.dump(hist, f, indent=4, ensure_ascii=False)

    @classmethod
    def carregar_layouts(cls) -> Dict:
        if not os.path.exists(cls.ARQUIVO_LAYOUTS): 
            return {"layouts": [], "ultimo_usado": None}
        try:
            with open(cls.ARQUIVO_LAYOUTS, 'r', encoding='utf-8') as f:
                return json.load(f)
        except: 
            return {"layouts": [], "ultimo_usado": None}

    @classmethod
    def salvar_layout(cls, nome: str, posicoes: List[Dict]):
        data = cls.carregar_layouts()
        data["layouts"] = [l for l in data["layouts"] if l["nome"] != nome]
        data["layouts"].append({
            "nome": nome,
            "posicoes": posicoes,
            "data_criacao": datetime.now().strftime("%Y-%m-%d %H:%M")
        })
        data["layouts"] = data["layouts"][-10:]
        data["ultimo_usado"] = nome
        with open(cls.ARQUIVO_LAYOUTS, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

    @classmethod
    def excluir_layout(cls, nome: str):
        data = cls.carregar_layouts()
        data["layouts"] = [l for l in data["layouts"] if l["nome"] != nome]
        if data["ultimo_usado"] == nome:
            data["ultimo_usado"] = None
        with open(cls.ARQUIVO_LAYOUTS, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

    # === NOVOS MÉTODOS PARA A BIBLIOTECA ===
    @classmethod
    def carregar_db_produtos(cls) -> Dict:
        """Carrega o banco de dados de produtos salvos"""
        if not os.path.exists(cls.ARQUIVO_DB_PRODUTOS): return {}
        try:
            with open(cls.ARQUIVO_DB_PRODUTOS, 'r', encoding='utf-8') as f:
                return json.load(f)
        except: return {}

    @classmethod
    def salvar_produto_db(cls, dados: Dict):
        """Salva um produto no banco de dados organizado por fornecedor"""
        db = cls.carregar_db_produtos()
        fornecedor = dados.get('Fornecedor', 'Sem Fornecedor').strip()
        nome_produto = dados.get('Produto', 'Sem Nome').strip()
        
        if not fornecedor: fornecedor = 'Outros'
        
        if fornecedor not in db:
            db[fornecedor] = {}
            
        # Salva o produto
        db[fornecedor][nome_produto] = dados
        
        with open(cls.ARQUIVO_DB_PRODUTOS, 'w', encoding='utf-8') as f:
            json.dump(db, f, indent=4, ensure_ascii=False)
            
    @classmethod
    def excluir_produto_db(cls, fornecedor, nome_produto):
        db = cls.carregar_db_produtos()
        if fornecedor in db and nome_produto in db[fornecedor]:
            del db[fornecedor][nome_produto]
            if not db[fornecedor]:
                del db[fornecedor]
            with open(cls.ARQUIVO_DB_PRODUTOS, 'w', encoding='utf-8') as f:
                json.dump(db, f, indent=4, ensure_ascii=False)

# === MOTOR DE GERAÇÃO PDF ===
class GeradorPDF:
    def __init__(self):
        self.cfg = EtiquetaConfig()

    def desenhar_layout(self, c, x, y, dados, img_path, logo_path, usar_img):
        """Desenha uma etiqueta individual"""
        # Fundo e Borda
        c.setFillColor(self.cfg.COR_FUNDO)
        c.rect(x, y, self.cfg.LARGURA, self.cfg.ALTURA, fill=1, stroke=0)
        c.setStrokeColor(HexColor('#CCCCCC'))
        c.setLineWidth(0.5)
        c.rect(x, y, self.cfg.LARGURA, self.cfg.ALTURA, fill=0, stroke=1)
        
        # Título
        c.setFillColor(self.cfg.COR_TEXTO)
        c.setFont("Helvetica-Bold", self.cfg.FONTE_TITULO)
        titulo_y = y + self.cfg.ALTURA - self.cfg.TITULO_Y_OFFSET
        c.drawCentredString(x + self.cfg.LARGURA/2, titulo_y, str(dados.get('Produto', '')))

        # Imagem
        img_limite_superior = titulo_y - self.cfg.IMG_MARGEM_TOPO
        boxes_topo = y + self.cfg.BOX_Y_BASE + self.cfg.BOX_ALTURA
        img_limite_inferior = boxes_topo + self.cfg.IMG_MARGEM_BASE
        img_altura_max = img_limite_superior - img_limite_inferior
        
        if usar_img and img_path and os.path.exists(img_path):
            try:
                img_x = x + (self.cfg.LARGURA - self.cfg.IMG_LARGURA_MAX) / 2
                c.drawImage(img_path, img_x, img_limite_inferior, 
                            width=self.cfg.IMG_LARGURA_MAX, height=img_altura_max, 
                            preserveAspectRatio=True, anchor='c', mask='auto')
            except:
                self._desenhar_placeholder_imagem(c, x, img_limite_inferior, self.cfg.IMG_LARGURA_MAX, img_altura_max)
        else:
            self._desenhar_placeholder_imagem(c, x, img_limite_inferior, self.cfg.IMG_LARGURA_MAX, img_altura_max)

        # Boxes
        bx = x + self.cfg.MARGEM
        by = y + self.cfg.BOX_Y_BASE
        self._desenhar_box(c, bx, by, "Especificações", dados.get('specs_list', []))

        bx2 = x + 53*mm
        self._desenhar_box_tamanhos(c, bx2, by, dados.get('tamanhos', []))

        # Rodapé
        by_rod = y + self.cfg.BOX_RODAPE_Y
        c.setStrokeColor(HexColor('#CCCCCC'))
        c.setLineWidth(0.8)
        c.roundRect(bx, by_rod, self.cfg.BOX_LARGURA, self.cfg.BOX_RODAPE_ALTURA, 2*mm)
        
        c.setFillColor(self.cfg.COR_TEXTO)
        c.setFont("Helvetica-Bold", self.cfg.FONTE_SUBTITULO)
        c.drawString(bx+3*mm, by_rod+20*mm, str(dados.get('Fornecedor', '')))
        c.setFont("Helvetica", 7)
        c.drawString(bx+3*mm, by_rod+15*mm, str(dados.get('Prazo', '')))

        # Logo
        if logo_path and os.path.exists(logo_path):
            try:
                logo_x = x + self.cfg.LARGURA - 43*mm
                logo_y = by_rod + 2*mm
                c.drawImage(logo_path, logo_x, logo_y, width=38*mm, height=24*mm, preserveAspectRatio=True, mask='auto')
            except: pass

    def _desenhar_placeholder_imagem(self, c, x_base, y_base, largura, altura):
        x_centro = x_base + (self.cfg.LARGURA - largura) / 2
        c.setStrokeColor(HexColor('#DDDDDD'))
        c.setFillColor(HexColor('#F9F9F9'))
        c.rect(x_centro, y_base, largura, altura, fill=1, stroke=1)
        c.setFillColor(HexColor('#BBBBBB'))
        c.setFont("Helvetica", 9)
        c.drawCentredString(x_base + self.cfg.LARGURA/2, y_base + altura/2, "📷 Sem imagem")

    def _desenhar_box(self, c, x, y, titulo, linhas):
        c.setLineWidth(0.8)
        c.roundRect(x, y, self.cfg.BOX_LARGURA, self.cfg.BOX_ALTURA, 2*mm)
        c.setFont("Helvetica-Bold", self.cfg.FONTE_SUBTITULO)
        c.drawCentredString(x + self.cfg.BOX_LARGURA/2, y + self.cfg.BOX_ALTURA - 7*mm, titulo)
        c.line(x+2*mm, y+self.cfg.BOX_ALTURA-10*mm, x+self.cfg.BOX_LARGURA-2*mm, y+self.cfg.BOX_ALTURA-10*mm)
        c.setFont("Helvetica", self.cfg.FONTE_SPECS)
        cur_y = y + self.cfg.BOX_ALTURA - 14*mm
        for linha in linhas:
            if linha and str(linha).strip():
                c.drawString(x+2*mm, cur_y, f"• {linha}")
                cur_y -= 4*mm

    def _desenhar_box_tamanhos(self, c, x, y, tamanhos):
        c.setLineWidth(0.8)
        c.roundRect(x, y, self.cfg.BOX_LARGURA, self.cfg.BOX_ALTURA, 2*mm)
        c.setFont("Helvetica-Bold", self.cfg.FONTE_SUBTITULO)
        c.drawCentredString(x + self.cfg.BOX_LARGURA/2, y + self.cfg.BOX_ALTURA - 7*mm, "Tamanhos")
        c.line(x+2*mm, y+self.cfg.BOX_ALTURA-10*mm, x+self.cfg.BOX_LARGURA-2*mm, y+self.cfg.BOX_ALTURA-10*mm)
        c.setFont("Helvetica", self.cfg.FONTE_TAMANHOS)
        cur_y = y + self.cfg.BOX_ALTURA - 14*mm
        for t in tamanhos:
            txt = f"{t.get('tamanho','')} - {t.get('medida','')} - {t.get('codigo','')}"
            c.drawString(x+2*mm, cur_y, txt)
            cur_y -= 3.5*mm

    def gerar_preview(self, dados, img_path, logo_path, usar_img, width=400):
        if not HAS_PDF2IMAGE: return None
        try:
            from reportlab.pdfgen import canvas
            buffer = io.BytesIO()
            c = canvas.Canvas(buffer, pagesize=(self.cfg.LARGURA, self.cfg.ALTURA))
            self.desenhar_layout(c, 0, 0, dados, img_path, logo_path, usar_img)
            c.save()
            buffer.seek(0)
            images = convert_from_bytes(buffer.read(), dpi=150)
            if images:
                img = images[0]
                ratio = width / img.width
                new_height = int(img.height * ratio)
                return img.resize((width, new_height), Image.Resampling.LANCZOS)
        except Exception as e:
            logger.error(f"Erro ao gerar preview: {e}")
            return None

# === JANELA DE CONFIGURAÇÃO DE POSIÇÕES ===
class JanelaConfiguracaoPosicoes(tk.Toplevel):
    def __init__(self, parent, dados_lista, gerador, img_path, logo_path, usar_img, callback_confirmar):
        super().__init__(parent)
        self.title("🎯 Configuração de Posições das Etiquetas")
        self.geometry("1000x750")
        self.resizable(False, False)
        
        self.dados_lista = dados_lista
        self.gerador = gerador
        self.img_path = img_path
        self.logo_path = logo_path
        self.usar_img = usar_img
        self.callback = callback_confirmar
        
        self.mapeamento_etiquetas = {}
        self.layouts_salvos = GerenciadorDados.carregar_layouts()
        
        self._criar_interface()
        
    def _criar_interface(self):
        header = tk.Frame(self, bg="#2c3e50", height=70)
        header.pack(fill="x")
        tk.Label(header, text="🎯 Configure onde cada etiqueta será impressa", 
                font=("Arial", 16, "bold"), bg="#2c3e50", fg="white").pack(pady=20)
        
        main = tk.Frame(self, padx=20, pady=20, bg="#ecf0f1")
        main.pack(fill="both", expand=True)
        
        # Painel Esquerdo
        left_panel = tk.Frame(main, bg="#ecf0f1")
        left_panel.pack(side="left", fill="both", expand=True, padx=(0, 10))
        
        info_frame = tk.Frame(left_panel, bg="#d5dbdb", relief="ridge", bd=2, padx=15, pady=10)
        info_frame.pack(fill="x", pady=(0, 15))
        tk.Label(info_frame, text="Clique em cada posição e selecione qual etiqueta colocar",
                font=("Arial", 10), bg="#d5dbdb", fg="#555").pack(anchor="w")
        
        grid_frame = tk.LabelFrame(left_panel, text="📄 Folha A4 - 4 Posições", 
                                   font=("Arial", 11, "bold"), padx=20, pady=20, bg="white")
        grid_frame.pack(fill="both", expand=True)
        
        self.frames_posicao = []
        self.labels_posicao = []
        
        posicoes_info = [
            ("Posição 1\nSuperior Esquerda", 0, 0),
            ("Posição 2\nSuperior Direita", 0, 1),
            ("Posição 3\nInferior Esquerda", 1, 0),
            ("Posição 4\nInferior Direita", 1, 1)
        ]
        
        for i, (texto, row, col) in enumerate(posicoes_info):
            frame_pos = tk.Frame(grid_frame, relief="solid", bd=3, bg="#ecf0f1", 
                                cursor="hand2", width=200, height=150)
            frame_pos.grid(row=row, column=col, padx=15, pady=15, sticky="nsew")
            frame_pos.grid_propagate(False)
            
            tk.Label(frame_pos, text=f"🔲 {i+1}", font=("Arial", 14, "bold"), 
                    bg="#ecf0f1", fg="#34495e").pack(pady=(10, 5))
            tk.Label(frame_pos, text=texto, font=("Arial", 8), bg="#ecf0f1", fg="#7f8c8d").pack()
            
            label_selecionada = tk.Label(frame_pos, text="[Vazio]", font=("Arial", 9, "bold"), 
                                        bg="#ecf0f1", fg="#95a5a6", wraplength=180)
            label_selecionada.pack(pady=(10, 5))
            
            btn = tk.Button(frame_pos, text="📌 Selecionar Etiqueta", 
                           command=lambda p=i: self._selecionar_etiqueta(p),
                           bg="#3498db", fg="white", font=("Arial", 8, "bold"), cursor="hand2")
            btn.pack(pady=(5, 10))
            
            self.frames_posicao.append(frame_pos)
            self.labels_posicao.append(label_selecionada)
        
        for i in range(2):
            grid_frame.grid_rowconfigure(i, weight=1)
            grid_frame.grid_columnconfigure(i, weight=1)
        
        # Painel Direito
        right_panel = tk.Frame(main, bg="#ecf0f1", width=300)
        right_panel.pack(side="right", fill="y")
        right_panel.pack_propagate(False)
        
        layout_frame = tk.LabelFrame(right_panel, text="💾 Layouts Salvos", font=("Arial", 10, "bold"), padx=10, pady=10)
        layout_frame.pack(fill="both", expand=True, pady=(0, 10))
        
        list_frame = tk.Frame(layout_frame)
        list_frame.pack(fill="both", expand=True, pady=5)
        scroll_layouts = ttk.Scrollbar(list_frame)
        scroll_layouts.pack(side="right", fill="y")
        self.lista_layouts = tk.Listbox(list_frame, font=("Arial", 9), yscrollcommand=scroll_layouts.set, height=10)
        self.lista_layouts.pack(side="left", fill="both", expand=True)
        scroll_layouts.config(command=self.lista_layouts.yview)
        
        tk.Button(layout_frame, text="📂 Carregar Layout", command=self._carregar_layout_selecionado, bg="#3498db", fg="white").pack(fill="x", pady=2)
        tk.Button(layout_frame, text="💾 Salvar Layout", command=self._salvar_layout_atual, bg="#27ae60", fg="white").pack(fill="x", pady=2)
        tk.Button(layout_frame, text="🗑️ Excluir Layout", command=self._excluir_layout_selecionado, bg="#e74c3c", fg="white").pack(fill="x", pady=2)
        
        action_frame = tk.Frame(self, bg="#ecf0f1", padx=20, pady=15)
        action_frame.pack(fill="x", side="bottom")
        tk.Button(action_frame, text="🔄 Limpar Tudo", command=self._limpar_mapeamento, bg="#95a5a6", fg="white").pack(side="left", padx=5)
        tk.Button(action_frame, text="✅ GERAR PDF", command=self._confirmar, bg="#27ae60", fg="white", font=("Arial", 12, "bold"), height=2, width=18).pack(side="right", padx=5)
        
        self._atualizar_lista_layouts()

    def _atualizar_lista_layouts(self):
        self.lista_layouts.delete(0, tk.END)
        for layout in self.layouts_salvos.get("layouts", []):
            self.lista_layouts.insert(tk.END, f"{layout['nome']} ({layout['data_criacao']})")

    def _selecionar_etiqueta(self, posicao):
        """Abre janela para escolher etiqueta da lista atual OU da biblioteca"""
        dialogo = tk.Toplevel(self)
        dialogo.title(f"Configurar Posição {posicao + 1}")
        dialogo.geometry("750x600")
        dialogo.transient(self)
        dialogo.grab_set()
        
        abas = ttk.Notebook(dialogo)
        abas.pack(fill="both", expand=True, padx=10, pady=10)
        
        # ABA 1: Lista Atual
        tab_atual = tk.Frame(abas)
        abas.add(tab_atual, text="📋 Lista Atual")
        lista_atual = tk.Listbox(tab_atual, font=("Arial", 10))
        lista_atual.pack(fill="both", expand=True, padx=5, pady=5)
        for i, dados in enumerate(self.dados_lista):
            p = dados.get('Produto', '')
            f = dados.get('Fornecedor', '')
            lista_atual.insert(tk.END, f"[{i+1}] {p} ({f})")

        # ABA 2: Biblioteca
        tab_db = tk.Frame(abas)
        abas.add(tab_db, text="🗄️ Biblioteca Salva (Por Fornecedor)")
        
        tree = ttk.Treeview(tab_db, columns=("Prazo"), show='tree headings')
        tree.heading("#0", text="Fornecedor / Produto")
        tree.heading("Prazo", text="Prazo")
        tree.column("#0", width=400)
        
        scroll_db = ttk.Scrollbar(tab_db, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scroll_db.set)
        tree.pack(side="left", fill="both", expand=True)
        scroll_db.pack(side="right", fill="y")
        
        db = GerenciadorDados.carregar_db_produtos()
        mapa_temp = {}
        
        for fornecedor, produtos in db.items():
            id_forn = tree.insert("", "end", text=fornecedor, open=False)
            for nome_prod, dados_prod in produtos.items():
                id_item = tree.insert(id_forn, "end", text=nome_prod, values=(dados_prod.get("Prazo", "")))
                mapa_temp[id_item] = dados_prod

        def confirmar():
            aba = abas.index("current")
            if aba == 0:
                sel = lista_atual.curselection()
                if not sel: return
                idx = sel[0]
                self.mapeamento_etiquetas[posicao] = idx
                self._atualizar_visual_posicao(posicao, idx)
            else:
                sel = tree.selection()
                if not sel: return
                item_id = sel[0]
                if item_id not in mapa_temp:
                    messagebox.showwarning("Atenção", "Selecione um produto, não o fornecedor.")
                    return
                
                # Adiciona do DB para a lista de impressão
                dados_db = mapa_temp[item_id]
                self.dados_lista.append(dados_db)
                novo_idx = len(self.dados_lista) - 1
                self.mapeamento_etiquetas[posicao] = novo_idx
                self._atualizar_visual_posicao(posicao, novo_idx)
            dialogo.destroy()

        tk.Button(dialogo, text="✅ CONFIRMAR SELEÇÃO", command=confirmar,
                  bg="#27ae60", fg="white", font=("Arial", 12, "bold"), height=2).pack(fill="x", padx=10, pady=10)

    def _atualizar_visual_posicao(self, posicao, idx_etiqueta):
        if idx_etiqueta is not None:
            produto = self.dados_lista[idx_etiqueta].get('Produto', 'Sem nome')
            self.labels_posicao[posicao].config(text=f"[{idx_etiqueta + 1}]\n{produto[:30]}...", fg="#2c3e50")
            self.frames_posicao[posicao].config(bg="#d5f4e6", bd=3, relief="solid")
        else:
            self.labels_posicao[posicao].config(text="[Vazio]", fg="#95a5a6")
            self.frames_posicao[posicao].config(bg="#ecf0f1", bd=3, relief="solid")

    def _carregar_layout_selecionado(self):
        sel = self.lista_layouts.curselection()
        if not sel: return
        idx = sel[0]
        layout = self.layouts_salvos["layouts"][idx]
        self.mapeamento_etiquetas.clear()
        for i, config in enumerate(layout["posicoes"]):
            if config.get("ativa") and config.get("etiqueta_idx") is not None:
                etq_idx = config["etiqueta_idx"]
                if etq_idx < len(self.dados_lista):
                    self.mapeamento_etiquetas[i] = etq_idx
                    self._atualizar_visual_posicao(i, etq_idx)
                else: self._atualizar_visual_posicao(i, None)
            else: self._atualizar_visual_posicao(i, None)
        messagebox.showinfo("Sucesso", f"Layout '{layout['nome']}' carregado!")

    def _salvar_layout_atual(self):
        if not self.mapeamento_etiquetas: return
        nome = simpledialog.askstring("Salvar", "Nome do layout:", parent=self)
        if nome:
            posicoes_config = []
            for i in range(4):
                if i in self.mapeamento_etiquetas:
                    posicoes_config.append({"ativa": True, "etiqueta_idx": self.mapeamento_etiquetas[i]})
                else:
                    posicoes_config.append({"ativa": False, "etiqueta_idx": None})
            GerenciadorDados.salvar_layout(nome.strip(), posicoes_config)
            self.layouts_salvos = GerenciadorDados.carregar_layouts()
            self._atualizar_lista_layouts()

    def _excluir_layout_selecionado(self):
        sel = self.lista_layouts.curselection()
        if not sel: return
        idx = sel[0]
        nome = self.layouts_salvos["layouts"][idx]["nome"]
        if messagebox.askyesno("Confirmar", f"Excluir '{nome}'?"):
            GerenciadorDados.excluir_layout(nome)
            self.layouts_salvos = GerenciadorDados.carregar_layouts()
            self._atualizar_lista_layouts()

    def _limpar_mapeamento(self):
        self.mapeamento_etiquetas.clear()
        for i in range(4): self._atualizar_visual_posicao(i, None)

    def _confirmar(self):
        if not self.mapeamento_etiquetas:
            messagebox.showwarning("Atenção", "Configure pelo menos uma posição!")
            return
        self.destroy()
        self.callback(self.mapeamento_etiquetas)

# === JANELA EDITOR DE CONFIGURAÇÃO ===
class EditorConfiguracao(tk.Toplevel):
    def __init__(self, parent, callback_atualizar):
        super().__init__(parent)
        self.title("⚙️ Editor de Tipos de Produtos")
        self.geometry("650x500")
        self.callback = callback_atualizar
        self.config = GerenciadorDados.carregar_config()
        
        frame_esq = tk.Frame(self, bg="#ecf0f1")
        frame_esq.pack(side="left", fill="y", padx=10, pady=10)
        tk.Label(frame_esq, text="Tipos Cadastrados", font=("Arial", 11, "bold"), bg="#ecf0f1").pack(pady=5)
        self.lista_tipos = tk.Listbox(frame_esq, width=25, height=20, font=("Arial", 9))
        self.lista_tipos.pack(pady=5)
        self.lista_tipos.bind('<<ListboxSelect>>', self._carregar_campos)
        tk.Button(frame_esq, text="➕ Novo Tipo", command=self._adicionar_tipo, bg="#2ecc71", fg="white").pack(fill="x", pady=2)
        tk.Button(frame_esq, text="🗑️ Excluir Tipo", command=self._remover_tipo, bg="#e74c3c", fg="white").pack(fill="x", pady=2)

        self.frame_dir = tk.LabelFrame(self, text="✏️ Campos do Produto", padx=15, pady=15, font=("Arial", 10, "bold"))
        self.frame_dir.pack(side="right", fill="both", expand=True, padx=10, pady=10)
        self.txt_campos = tk.Text(self.frame_dir, height=18, width=35, font=("Arial", 10))
        self.txt_campos.pack(fill="both", expand=True, pady=5)
        tk.Button(self.frame_dir, text="💾 SALVAR ALTERAÇÕES", command=self._salvar_tudo, bg="#27ae60", fg="white", height=2).pack(fill="x", pady=10)
        self._atualizar_lista()

    def _atualizar_lista(self):
        self.lista_tipos.delete(0, tk.END)
        for tipo in self.config: self.lista_tipos.insert(tk.END, tipo)

    def _carregar_campos(self, event):
        sel = self.lista_tipos.curselection()
        if not sel: return
        tipo = self.lista_tipos.get(sel)
        campos = self.config[tipo].get("campos", [])
        self.txt_campos.delete("1.0", tk.END)
        self.txt_campos.insert("1.0", "\n".join(campos))

    def _adicionar_tipo(self):
        novo = simpledialog.askstring("Novo", "Nome do tipo:")
        if novo and novo.strip():
            if novo in self.config: return
            self.config[novo] = {"campos": ["Campo 1"], "placeholders": {}}
            self._atualizar_lista()

    def _remover_tipo(self):
        sel = self.lista_tipos.curselection()
        if sel:
            tipo = self.lista_tipos.get(sel)
            if messagebox.askyesno("Confirmar", f"Excluir '{tipo}'?"):
                del self.config[tipo]
                self._atualizar_lista()
                self.txt_campos.delete("1.0", tk.END)

    def _salvar_tudo(self):
        sel = self.lista_tipos.curselection()
        if sel:
            tipo = self.lista_tipos.get(sel)
            texto = self.txt_campos.get("1.0", tk.END).strip()
            self.config[tipo]['campos'] = [x.strip() for x in texto.split('\n') if x.strip()]
        GerenciadorDados.salvar_config(self.config)
        self.callback()
        self.destroy()

# === APLICAÇÃO PRINCIPAL ===
class AppFortunne:
    def __init__(self, root):
        self.root = root
        self.root.title("Fortunne Label System V10.0 - Enterprise Edition")
        self.root.geometry("950x1000")
        
        style = ttk.Style()
        style.theme_use('clam')
        
        self.config_produtos = GerenciadorDados.carregar_config()
        self.historico = GerenciadorDados.carregar_historico()
        
        self.path_logo = tk.StringVar()
        self.path_img = tk.StringVar()
        self.path_excel = tk.StringVar()
        self.tipo_produto = tk.StringVar()
        self.nome_pdf = tk.StringVar(value="Etiquetas_Fortunne")
        self.usar_img = tk.BooleanVar(value=True)
        self.quantidade = tk.IntVar(value=1)

        self._init_ui()

    def _init_ui(self):
        top = tk.Frame(self.root, bg="#2c3e50", height=70)
        top.pack(fill="x")
        tk.Label(top, text="🏢 FORTUNNE", font=("Helvetica", 20, "bold"), bg="#2c3e50", fg="white").pack(side="left", padx=20, pady=15)
        tk.Button(top, text="⚙️ Configurar Tipos", command=self._abrir_editor_config, bg="#34495e", fg="white").place(relx=0.85, rely=0.25)

        main = tk.Frame(self.root, bg="#ecf0f1")
        main.pack(fill="both", expand=True, padx=15, pady=15)
        
        canvas = tk.Canvas(main, bg="#ecf0f1")
        scroll = ttk.Scrollbar(main, orient="vertical", command=canvas.yview)
        self.conteudo = tk.Frame(canvas, bg="#ecf0f1")
        self.conteudo.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self.conteudo, anchor="nw")
        canvas.configure(yscrollcommand=scroll.set)
        canvas.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        self._montar_formulario()

    def _montar_formulario(self):
        # Arquivos
        fr_files = tk.LabelFrame(self.conteudo, text="📂 Arquivos e Mídia", font=("Arial", 11, "bold"), bg="#fff", padx=10, pady=10)
        fr_files.pack(fill="x", padx=5, pady=8)
        self._input_file(fr_files, "Logo Empresa:", self.path_logo)
        self._input_file(fr_files, "Imagem Produto:", self.path_img)
        tk.Checkbutton(fr_files, text="✓ Incluir imagem", variable=self.usar_img, bg="#fff").pack(anchor="w")

        # Tabs
        self.tabs = ttk.Notebook(self.conteudo)
        self.tabs.pack(fill="both", expand=True, padx=5, pady=10)
        self._tab_manual()
        self._tab_excel()

        # Gerar
        fr_action = tk.LabelFrame(self.conteudo, text="🚀 Geração", font=("Arial", 11, "bold"), bg="#fff", padx=15, pady=15)
        fr_action.pack(fill="x", padx=5, pady=10)
        tk.Label(fr_action, text="Nome arquivo:", bg="#fff").pack(side="left")
        tk.Entry(fr_action, textvariable=self.nome_pdf, width=30).pack(side="left", padx=5)
        
        btn_cont = tk.Frame(fr_action, bg="#fff")
        btn_cont.pack(side="right", fill="x")
        tk.Button(btn_cont, text="👁️ Preview", command=self.visualizar_preview, bg="#9b59b6", fg="white").pack(side="left", padx=5)
        tk.Button(btn_cont, text="🎯 GERAR PDF", command=self.configurar_posicoes, bg="#2980b9", fg="white", height=2).pack(side="left", padx=5)

    def _input_file(self, parent, label, var):
        f = tk.Frame(parent, bg="#fff")
        f.pack(fill="x", pady=2)
        tk.Label(f, text=label, width=15, anchor="w", bg="#fff").pack(side="left")
        tk.Entry(f, textvariable=var, state="readonly").pack(side="left", fill="x", expand=True)
        tk.Button(f, text="📁", command=lambda: self._buscar_arq(var)).pack(side="right")

    def _buscar_arq(self, var):
        f = filedialog.askopenfilename()
        if f: var.set(f)

    def _tab_manual(self):
        f_man = tk.Frame(self.tabs, bg="#fff")
        self.tabs.add(f_man, text="✏️ Cadastro Manual")
        
        fr_sel = tk.Frame(f_man, pady=15, bg="#fff")
        fr_sel.pack(fill="x")
        tk.Label(fr_sel, text="Tipo:", bg="#fff").pack(side="left", padx=10)
        chaves = list(self.config_produtos.keys())
        self.combo_tipo = ttk.Combobox(fr_sel, textvariable=self.tipo_produto, values=chaves, state="readonly")
        self.combo_tipo.pack(side="left", padx=5)
        self.combo_tipo.bind("<<ComboboxSelected>>", self._render_form)
        if chaves: self.combo_tipo.current(0)
        
        tk.Label(fr_sel, text="Qtd:", bg="#fff").pack(side="left", padx=10)
        tk.Spinbox(fr_sel, from_=1, to=100, textvariable=self.quantidade, width=5).pack(side="left")

        canvas_form = tk.Canvas(f_man, bg="#fff")
        scroll_form = ttk.Scrollbar(f_man, orient="vertical", command=canvas_form.yview)
        self.container_campos = tk.Frame(canvas_form, bg="#fff")
        self.container_campos.bind("<Configure>", lambda e: canvas_form.configure(scrollregion=canvas_form.bbox("all")))
        canvas_form.create_window((0, 0), window=self.container_campos, anchor="nw")
        canvas_form.configure(yscrollcommand=scroll_form.set)
        canvas_form.pack(side="left", fill="both", expand=True)
        scroll_form.pack(side="right", fill="y")
        
        self.vars_campos = {}
        self.vars_tamanhos = []
        
        # Botão Salvar DB
        fr_bot = tk.Frame(f_man, bg="#fff", pady=10)
        fr_bot.pack(fill="x", side="bottom")
        tk.Button(fr_bot, text="💾 SALVAR NA BIBLIOTECA", command=self._salvar_na_biblioteca, 
                  bg="#e67e22", fg="white", font=("Arial", 10, "bold"), height=2).pack(fill="x", padx=20)

        if chaves: self._render_form()

    def _salvar_na_biblioteca(self):
        dados = self._coletar_manual()
        if not dados:
            messagebox.showwarning("Atenção", "Preencha os dados!")
            return
        GerenciadorDados.salvar_produto_db(dados)
        messagebox.showinfo("Salvo", f"Produto '{dados['Produto']}' salvo na biblioteca!")

    def _render_form(self, event=None):
        for w in self.container_campos.winfo_children(): w.destroy()
        tipo = self.tipo_produto.get()
        cfg = self.config_produtos.get(tipo, {})
        campos = cfg.get("campos", [])
        placeholders = cfg.get("placeholders", {})
        
        self.vars_campos = {}
        self.vars_tamanhos = []
        
        self._criar_input(self.container_campos, "Produto", "Nome", 0)
        for i, c in enumerate(campos):
            self._criar_input(self.container_campos, c, placeholders.get(c, ""), i+1, auto=True)
        
        last = len(campos) + 1
        self._criar_input(self.container_campos, "Fornecedor", "Nome", last, auto=True)
        self._criar_input(self.container_campos, "Prazo", "Dias", last+1)
        
        # Tamanhos
        fr = tk.LabelFrame(self.container_campos, text="Tamanhos", bg="#fff")
        fr.grid(row=last+2, column=0, columnspan=2, sticky="ew", pady=10)
        tk.Label(fr, text="Tam / Med / Cod", bg="#fff").pack()
        for i in range(5):
            f = tk.Frame(fr, bg="#fff")
            f.pack()
            l = []
            for j in range(3):
                v = tk.StringVar()
                tk.Entry(f, textvariable=v, width=15).pack(side="left")
                l.append(v)
            self.vars_tamanhos.append(l)

    def _criar_input(self, parent, label, ph, row, auto=False):
        tk.Label(parent, text=label, bg="#fff").grid(row=row, column=0, sticky="w", pady=2)
        if auto and label in self.historico:
            var = tk.StringVar()
            ttk.Combobox(parent, textvariable=var, values=self.historico[label]).grid(row=row, column=1, sticky="ew")
        else:
            var = tk.StringVar()
            tk.Entry(parent, textvariable=var).grid(row=row, column=1, sticky="ew")
        self.vars_campos[label] = var

    def _coletar_manual(self) -> Optional[Dict]:
        dados = {}
        for campo, var in self.vars_campos.items():
            dados[campo] = var.get().strip()
        
        if not dados.get('Produto'): return None
        
        tipo = self.tipo_produto.get()
        campos = self.config_produtos.get(tipo, {}).get('campos', [])
        dados['specs_list'] = [f"{c}: {dados[c]}" for c in campos if c in dados and dados[c]]
        
        tams = []
        for l in self.vars_tamanhos:
            t, m, c = l[0].get(), l[1].get(), l[2].get()
            if t or m or c: tams.append({'tamanho': t, 'medida': m, 'codigo': c})
        dados['tamanhos'] = tams
        return dados

    def _tab_excel(self):
        f_xl = tk.Frame(self.tabs, bg="#fff")
        self.tabs.add(f_xl, text="📊 Excel")
        
        tk.Label(f_xl, text="Tipo:", bg="#fff").pack()
        self.combo_tipo_excel = ttk.Combobox(f_xl, values=list(self.config_produtos.keys()))
        self.combo_tipo_excel.pack()
        if self.config_produtos: self.combo_tipo_excel.current(0)
        
        tk.Button(f_xl, text="Gerar Modelo", command=self._gerar_template_excel).pack(pady=5)
        
        tk.Label(f_xl, text="Arquivo:", bg="#fff").pack()
        fr = tk.Frame(f_xl, bg="#fff")
        fr.pack()
        tk.Entry(fr, textvariable=self.path_excel).pack(side="left")
        tk.Button(fr, text="...", command=lambda: self._buscar_arq(self.path_excel)).pack(side="left")

    def _gerar_template_excel(self):
        tipo = self.combo_tipo_excel.get()
        if not tipo: return
        campos = self.config_produtos[tipo]['campos']
        cols = ['Produto', 'Fornecedor', 'Prazo'] + campos + ['Tam1', 'Med1', 'Cod1']
        df = pd.DataFrame(columns=cols)
        f = filedialog.asksaveasfilename(defaultextension=".xlsx")
        if f: 
            df.to_excel(f, index=False)
            messagebox.showinfo("Sucesso", "Modelo gerado!")

    def _ler_excel(self):
        try:
            df = pd.read_excel(self.path_excel.get())
            lista = []
            tipo = self.combo_tipo_excel.get()
            campos = self.config_produtos.get(tipo, {}).get('campos', [])
            
            for idx, row in df.iterrows():
                if pd.isna(row.get('Produto')): continue
                d = {'Produto': str(row['Produto']), 'Fornecedor': str(row.get('Fornecedor','')), 'Prazo': str(row.get('Prazo',''))}
                d['specs_list'] = [f"{c}: {row.get(c,'')}" for c in campos if not pd.isna(row.get(c))]
                
                tams = []
                # Simplificado para 1 tamanho no exemplo, expandir conforme necessidade
                if not pd.isna(row.get('Tam1')):
                    tams.append({'tamanho': str(row['Tam1']), 'medida': str(row.get('Med1','')), 'codigo': str(row.get('Cod1',''))})
                d['tamanhos'] = tams
                lista.append(d)
            return lista
        except Exception as e:
            messagebox.showerror("Erro", str(e))
            return []

    def visualizar_preview(self):
        if not HAS_PDF2IMAGE:
            messagebox.showinfo("Aviso", "Instale pdf2image para ver o preview.")
            return
        
        dados = self._coletar_manual()
        if not dados: return
        
        win = tk.Toplevel(self.root)
        win.title("Preview")
        gen = GeradorPDF()
        img = gen.gerar_preview(dados, self.path_img.get(), self.path_logo.get(), self.usar_img.get())
        if img:
            ph = ImageTk.PhotoImage(img)
            lbl = tk.Label(win, image=ph)
            lbl.image = ph
            lbl.pack()

    def configurar_posicoes(self):
        if self.tabs.index("current") == 0:
            d = self._coletar_manual()
            if not d: return
            lista = [d] * self.quantidade.get()
        else:
            lista = self._ler_excel()
            if not lista: return
            
        gen = GeradorPDF()
        JanelaConfiguracaoPosicoes(self.root, lista, gen, self.path_img.get(), self.path_logo.get(), self.usar_img.get(), 
                                   lambda m: self._gerar_pdf_final(lista, m, gen))

    def _gerar_pdf_final(self, lista, mapeamento, gen):
        f = filedialog.asksaveasfilename(defaultextension=".pdf")
        if not f: return
        try:
            c = canvas.Canvas(f, pagesize=A4)
            larg, alt = A4
            posicoes = [(0, alt/2), (larg/2, alt/2), (0, 0), (larg/2, 0)]
            
            usados = set()
            for i in range(4):
                if i in mapeamento:
                    idx = mapeamento[i]
                    usados.add(idx)
                    x, y = posicoes[i]
                    gen.desenhar_layout(c, x, y, lista[idx], self.path_img.get(), self.path_logo.get(), self.usar_img.get())
            
            c.showPage()
            c.save()
            messagebox.showinfo("Sucesso", "PDF Gerado!")
        except Exception as e:
            messagebox.showerror("Erro", str(e))

    def _abrir_editor_config(self):
        EditorConfiguracao(self.root, lambda: [self._init_ui()]) # Recarrega simples

if __name__ == "__main__":
    root = tk.Tk()
    app = AppFortunne(root)
    root.mainloop()