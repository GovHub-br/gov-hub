"""
Hook para corrigir caminhos de assets em todos os arquivos HTML gerados pelo MkDocs
Converte caminhos relativos de assets para caminhos absolutos baseados no site_url
"""
import re
from pathlib import Path
from mkdocs.config.defaults import MkDocsConfig


def on_post_build(config: MkDocsConfig, **kwargs):
    """
    Corrige caminhos de assets em todos os arquivos HTML gerados
    Converte caminhos relativos ../assets/ para caminhos absolutos /govhub/assets/
    """
    # Extrai o base path do site_url (ex: /govhub/ de https://govhub.github.io/govhub/)
    site_url = config.site_url or ""
    base_path = ""
    if site_url:
        from urllib.parse import urlparse
        parsed = urlparse(site_url)
        base_path = parsed.path.rstrip('/')
        if base_path and not base_path.startswith('/'):
            base_path = '/' + base_path
    
    if not base_path:
        print("⚠️ site_url não configurado, pulando correção de caminhos")
        return
    
    site_dir = Path(config.site_dir)
    
    # Processa todos os arquivos HTML no diretório site
    html_files = list(site_dir.rglob("*.html"))
    
    for html_file in html_files:
        try:
            with open(html_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            original_content = content
            
            # Converte caminhos relativos de assets para absolutos
            # Padrão: href="../assets/..." ou src="../assets/..."
            def fix_asset_path(match):
                attr = match.group(1)  # href ou src
                quote = match.group(2)  # " ou '
                path = match.group(3)   # o caminho
                
                # Se já é um caminho absoluto, mantém como está
                if path.startswith('/') or path.startswith('http://') or path.startswith('https://'):
                    return match.group(0)
                
                # Se começa com ../assets/, converte para caminho absoluto
                if path.startswith('../assets/'):
                    new_path = path.replace('../assets/', f'{base_path}/assets/', 1)
                    return f'{attr}={quote}{new_path}{quote}'
                
                # Se começa com ./assets/, converte para caminho absoluto
                if path.startswith('./assets/'):
                    new_path = path.replace('./assets/', f'{base_path}/assets/', 1)
                    return f'{attr}={quote}{new_path}{quote}'
                
                # Se começa com assets/ (sem ./ ou ../), converte para caminho absoluto
                if path.startswith('assets/'):
                    new_path = f'{base_path}/{path}'
                    return f'{attr}={quote}{new_path}{quote}'
                
                # Mantém outros caminhos como estão
                return match.group(0)
            
            # Aplica a correção em href e src
            content = re.sub(
                r'(href|src)=(["\'])([^"\']+)["\']',
                fix_asset_path,
                content
            )
            
            # Também corrige caminhos em url() dentro de CSS inline
            def fix_css_url(match):
                quote = match.group(1) or ''  # " ou ' ou vazio
                url_path = match.group(2)
                
                # Se já é um caminho absoluto, mantém como está
                if url_path.startswith('/') or url_path.startswith('http://') or url_path.startswith('https://'):
                    return match.group(0)
                
                # Se começa com ../assets/, converte para caminho absoluto
                if url_path.startswith('../assets/'):
                    new_path = url_path.replace('../assets/', f'{base_path}/assets/', 1)
                    return f'url({quote}{new_path}{quote})'
                
                # Se começa com ./assets/, converte para caminho absoluto
                if url_path.startswith('./assets/'):
                    new_path = url_path.replace('./assets/', f'{base_path}/assets/', 1)
                    return f'url({quote}{new_path}{quote})'
                
                # Se começa com assets/, converte para caminho absoluto
                if url_path.startswith('assets/'):
                    new_path = f'{base_path}/{url_path}'
                    return f'url({quote}{new_path}{quote})'
                
                # Mantém outros caminhos como estão
                return match.group(0)
            
            content = re.sub(
                r'url\((["\']?)([^"\'()]+)\1\)',
                fix_css_url,
                content
            )
            
            # Só escreve se houve mudanças
            if content != original_content:
                with open(html_file, 'w', encoding='utf-8') as f:
                    f.write(content)
                print(f"✅ Corrigidos caminhos de assets em {html_file.relative_to(site_dir)}")
        
        except Exception as e:
            print(f"⚠️ Erro ao processar {html_file}: {e}")

