"""
Hook para copiar o index.html da landing page para a raiz do site gerado
"""
import shutil
import re
from pathlib import Path
from mkdocs.config.defaults import MkDocsConfig


def on_post_build(config: MkDocsConfig, **kwargs):
    """
    Copia o arquivo docs/home/index.html para a raiz do site gerado
    e ajusta os caminhos relativos para apontar corretamente
    """
    # Caminho do arquivo HTML da landing page
    source_file = Path(config.docs_dir) / "home" / "index.html"
    
    # Caminho de destino (raiz do site gerado)
    dest_file = Path(config.site_dir) / "index.html"
    
    # Extrai o base path do site_url (ex: /govhub/ de https://govhub.github.io/govhub/)
    site_url = config.site_url or ""
    base_path = ""
    if site_url:
        from urllib.parse import urlparse
        parsed = urlparse(site_url)
        base_path = parsed.path.rstrip('/')
        if base_path and not base_path.startswith('/'):
            base_path = '/' + base_path
    
    # Verifica se o arquivo fonte existe
    if source_file.exists():
        # Lê o conteúdo do arquivo
        with open(source_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Ajusta apenas caminhos relativos que começam com ./
        # Mantém caminhos absolutos /govhub/... intactos (já estão corretos)
        # Mantém caminhos ../ intactos (links para documentação do MkDocs)
        
        # Ajusta href e src
        def adjust_attr(match):
            attr = match.group(1)  # href ou src
            path = match.group(2)   # o caminho
            
            # Se já é um caminho absoluto começando com /govhub/, mantém como está
            if path.startswith('/govhub/') or path.startswith(base_path + '/'):
                return match.group(0)
            
            # Se começa com ./, ajusta para land/dist/ ou mantém se for arquivo local
            if path.startswith('./'):
                # Se for um arquivo JS/CSS local (ex: ./index.js), mantém relativo
                # Se for um recurso de land/dist, converte para absoluto
                if path.endswith(('.js', '.css')) and not path.startswith('./land/'):
                    # Mantém como está (arquivo local)
                    return match.group(0)
                else:
                    # Converte para caminho absoluto
                    new_path = path.replace('./', f'{base_path}/land/dist/', 1)
                    return f'{attr}="{new_path}"'
            
            # Mantém outros caminhos (../, URLs externas, etc.) como estão
            return match.group(0)
        
        content = re.sub(r'(href|src)=["\']([^"\']+)["\']', adjust_attr, content)
        
        # Ajusta também caminhos em url() dentro de CSS
        def adjust_url(match):
            url_path = match.group(1)
            
            # Se já é um caminho absoluto, mantém como está
            if url_path.startswith('/govhub/') or url_path.startswith(base_path + '/'):
                return match.group(0)
            
            # Se começa com ./, ajusta para land/dist/
            if url_path.startswith('./'):
                new_path = url_path.replace('./', f'{base_path}/land/dist/', 1)
                return f'url({new_path})'
            
            # Mantém outros caminhos como estão
            return match.group(0)
        
        content = re.sub(r'url\(["\']?([^"\'()]+)["\']?\)', adjust_url, content)
        
        # Escreve o arquivo ajustado
        with open(dest_file, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"✅ Copiado e ajustado {source_file} para {dest_file}")
    else:
        print(f"⚠️ Arquivo não encontrado: {source_file}")

