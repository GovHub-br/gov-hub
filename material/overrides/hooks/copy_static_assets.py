"""
Hook para copiar diretórios estáticos (global-assets e land/dist) e páginas HTML para o site gerado
Tanto na raiz quanto em /govhub/ para funcionar localmente e remotamente
"""
import shutil
from pathlib import Path
from mkdocs.config.defaults import MkDocsConfig


def on_post_build(config: MkDocsConfig, **kwargs):
    """
    Copia os diretórios global-assets, land/dist e páginas HTML para o site gerado
    Tanto na raiz quanto em /govhub/ para funcionar localmente e remotamente
    """
    docs_dir = Path(config.docs_dir)
    site_dir = Path(config.site_dir)
    
    # Extrai o base path do site_url (ex: /govhub/ de https://govhub.github.io/govhub/)
    site_url = config.site_url or ""
    base_path = ""
    if site_url:
        from urllib.parse import urlparse
        parsed = urlparse(site_url)
        base_path = parsed.path.rstrip('/')
        if base_path and not base_path.startswith('/'):
            base_path = '/' + base_path
    
    # Diretórios estáticos a copiar
    static_dirs_to_copy = [
        ('global-assets', 'global-assets'),
        ('land/dist', 'land/dist'),
        ('land/public', 'land/public'),
    ]
    
    for source_rel, dest_rel in static_dirs_to_copy:
        source_dir = docs_dir / source_rel
        
        dest_dir_root = site_dir / dest_rel
        if source_dir.exists() and source_dir.is_dir():
            if dest_dir_root.exists():
                shutil.rmtree(dest_dir_root)
            shutil.copytree(source_dir, dest_dir_root)
            print(f"✅ Copiado {source_rel} para {dest_rel}")
        else:
            print(f"⚠️ Diretório não encontrado: {source_dir}")
        
        if base_path:
            base_path_clean = base_path.lstrip('/')
            dest_dir_base = site_dir / base_path_clean / dest_rel
            if source_dir.exists() and source_dir.is_dir():
                dest_dir_base.parent.mkdir(parents=True, exist_ok=True)
                if dest_dir_base.exists():
                    shutil.rmtree(dest_dir_base)
                shutil.copytree(source_dir, dest_dir_base)
                print(f"✅ Copiado {source_rel} para {base_path}/{dest_rel}")
    
    # Copia todas as páginas geradas pelo MkDocs para base_path
    if base_path:
        base_path_clean = base_path.lstrip('/')
        dest_base_dir = site_dir / base_path_clean
        
        ignore_dirs = {'global-assets', 'land', 'govhub'}
        ignore_files = {'sitemap.xml', 'sitemap.xml.gz', 'schema.json', '404.html', 'index.html'}
        
        for item in site_dir.iterdir():
            if (item.is_dir() and item.name in ignore_dirs) or \
               (item.is_file() and (item.name in ignore_files or item.suffix == '.map')):
                continue
            
            dest_item = dest_base_dir / item.name
            try:
                if item.is_dir():
                    dest_item.parent.mkdir(parents=True, exist_ok=True)
                    if dest_item.exists():
                        shutil.rmtree(dest_item)
                    shutil.copytree(item, dest_item)
                    print(f"✅ Copiado {item.name}/ para {base_path}/{item.name}/")
                elif item.is_file():
                    dest_item.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(item, dest_item)
                    print(f"✅ Copiado {item.name} para {base_path}/{item.name}")
            except Exception as e:
                print(f"⚠️ Erro ao copiar {item.name}: {e}")
