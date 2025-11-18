"""
Hook para copiar o index.html da landing page para a raiz do site gerado
"""
import shutil
import re
from pathlib import Path
from mkdocs.config.defaults import MkDocsConfig


def on_post_build(config: MkDocsConfig, **kwargs):
    """
    Copia o arquivo docs/land/dist/index.html para a raiz do site gerado
    e ajusta os caminhos relativos para apontar para land/dist/
    """
    # Caminho do arquivo HTML da landing page
    source_file = Path(config.docs_dir) / "land" / "dist" / "index.html"
    
    # Caminho de destino (raiz do site gerado)
    dest_file = Path(config.site_dir) / "index.html"
    
    # Verifica se o arquivo fonte existe
    if source_file.exists():
        # Lê o conteúdo do arquivo
        with open(source_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Ajusta os caminhos relativos que começam com ./
        # Mantém os caminhos ../ intactos (links para documentação do MkDocs)
        # Ajusta apenas caminhos ./ para land/dist/
        
        # Ajusta href e src que começam com ./
        def adjust_attr(match):
            attr = match.group(1)  # href ou src
            path = match.group(2)   # o caminho
            # Se começa com ../, mantém (links para documentação)
            if path.startswith('../'):
                return match.group(0)
            # Se começa com ./, ajusta para land/dist/
            if path.startswith('./'):
                new_path = path.replace('./', 'land/dist/', 1)
                return f'{attr}="{new_path}"'
            return match.group(0)
        
        content = re.sub(r'(href|src)=["\'](\./[^"\']+)["\']', adjust_attr, content)
        
        # Ajusta também caminhos em url() dentro de CSS
        def adjust_url(match):
            url_path = match.group(1)
            if url_path.startswith('../'):
                return match.group(0)
            if url_path.startswith('./'):
                new_path = url_path.replace('./', 'land/dist/', 1)
                return f'url({new_path})'
            return match.group(0)
        
        content = re.sub(r'url\(["\']?(\./[^"\'()]+)["\']?\)', adjust_url, content)
        
        # Escreve o arquivo ajustado
        with open(dest_file, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"✅ Copiado e ajustado {source_file} para {dest_file}")
    else:
        print(f"⚠️ Arquivo não encontrado: {source_file}")

