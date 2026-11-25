import requests
import streamlit as st


def _limpar_categoria_off(produto: dict) -> str:
    """Extrai e formata a categoria principal vinda da Open Food/Beauty Facts."""
    tags = produto.get("categories_tags", [])
    if isinstance(tags, list) and tags:
        tags_pt = [t for t in tags if str(t).startswith("pt:")]
        escolhida = tags_pt[-1] if tags_pt else tags[-1]
        nome_limpo = str(escolhida).split(":", 1)[-1].replace("-", " ").strip()
        if nome_limpo:
            return nome_limpo.title()

    cats_texto = str(produto.get("categories", "")).strip()
    if cats_texto:
        partes = [p.strip() for p in cats_texto.split(",") if p.strip()]
        if partes:
            return partes[-1].split(":", 1)[-1].strip().title()

    return ""


@st.cache_data(ttl=3600)
def buscar_dados_mestres(ean: str) -> dict:
    ean_limpo = "".join(filter(str.isdigit, str(ean)))
    headers = {"User-Agent": "MVPInteligenciaVarejo/1.0"}

    # 1. Busca gratuita: Open Food Facts e Open Beauty Facts
    for dominio in ["world.openfoodfacts.org", "world.openbeautyfacts.org"]:
        try:
            r = requests.get(
                f"https://{dominio}/api/v2/product/{ean_limpo}.json",
                headers=headers,
                timeout=5,
            )
            if r.status_code == 200 and r.json().get("status") == 1:
                p = r.json().get("product", {})
                nome = (
                    p.get("product_name_pt")
                    or p.get("product_name")
                    or p.get("generic_name")
                )
                if nome:
                    return {
                        "descricao": nome,
                        "categoria": _limpar_categoria_off(p),
                        "marca": p.get("brands", ""),
                        "ncm": "",
                        "unidade": p.get("quantity", "UN"),
                    }
        except Exception:
            pass

    # 2. Fallback gratuito: UPCitemdb
    try:
        r = requests.get(
            f"https://api.upcitemdb.com/prod/trial/lookup?upc={ean_limpo}",
            headers=headers,
            timeout=5,
        )
        if r.status_code == 200:
            itens = r.json().get("items", [])
            if itens:
                item = itens[0]
                cat_upc = str(item.get("category", "")).strip()
                if ">" in cat_upc:
                    cat_upc = cat_upc.split(">")[-1].strip()
                return {
                    "descricao": item.get("title", ""),
                    "categoria": cat_upc,
                    "marca": item.get("brand", ""),
                    "ncm": "",
                    "unidade": item.get("size", "UN") or "UN",
                }
    except Exception:
        pass

    return {"descricao": "", "categoria": "", "marca": "", "ncm": "", "unidade": "UN"}
