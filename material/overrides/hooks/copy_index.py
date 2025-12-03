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
        
        # Ajusta caminhos relativos (./) para absolutos, mantém caminhos absolutos intactos
        def adjust_attr(match):
            attr = match.group(1)  # href ou src
            path = match.group(2)   # o caminho
            
            if path.startswith('/govhub/') or path.startswith(base_path + '/'):
                return match.group(0)
            
            # Se começa com ./, ajusta para caminho absoluto
            if path.startswith('./'):
                if path.endswith(('.js', '.css')) and not path.startswith('./land/'):
                    new_path = path.replace('./', f'{base_path}/home/', 1)
                    return f'{attr}="{new_path}"'
                else:
                    new_path = path.replace('./', f'{base_path}/land/dist/', 1)
                    return f'{attr}="{new_path}"'
            
            return match.group(0)
        
        content = re.sub(r'(href|src)=["\']([^"\']+)["\']', adjust_attr, content)
        
        def adjust_url(match):
            url_path = match.group(1)
            
            if url_path.startswith('/govhub/') or url_path.startswith(base_path + '/'):
                return match.group(0)
            
            # Se começa com ./, ajusta para caminho absoluto
            if url_path.startswith('./'):
                if url_path.endswith(('.js', '.css')) and not url_path.startswith('./land/'):
                    new_path = url_path.replace('./', f'{base_path}/home/', 1)
                else:
                    new_path = url_path.replace('./', f'{base_path}/land/dist/', 1)
                return f'url({new_path})'
            
            return match.group(0)
        
        content = re.sub(r'url\(["\']?([^"\'()]+)["\']?\)', adjust_url, content)
        
        # Escreve o arquivo ajustado
        with open(dest_file, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"✅ Copiado e ajustado {source_file} para {dest_file}")
    else:
        print(f"⚠️ Arquivo não encontrado: {source_file}")

