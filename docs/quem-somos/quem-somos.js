// ========================================
// QUEM SOMOS - JAVASCRIPT FILE
// ========================================

// Função para preload das imagens da equipe
function preloadTeamImages() {
    const teamImages = [
        // UnB Team
        '/govhub/land/dist/images/equipe/alex_reis.png',
        '/govhub/land/dist/images/equipe/carla.png',
        '/govhub/land/dist/images/equipe/laila.png',
        '/govhub/land/dist/images/equipe/isaque.png',
        '/govhub/land/dist/images/equipe/joao.png',
        '/govhub/land/dist/images/equipe/arthur.png',
        '/govhub/land/dist/images/equipe/davi.png',
        '/govhub/land/dist/images/equipe/joyce.png',
        '/govhub/land/dist/images/equipe/mateus.png',
        '/govhub/land/dist/images/equipe/guilherme_gusmao.jpg',
        '/govhub/land/dist/images/equipe/vinicius.png',
        
        // IPEA Team
        '/govhub/land/dist/images/equipe/fernando_gaiger.png',
        '/govhub/land/dist/images/equipe/gustavo_camilo.png',
        
        // Parceiros
        '/govhub/land/dist/images/equipe/joao_freitas.jpeg',
        '/govhub/land/dist/images/equipe/matheus_dias.jpeg',
        '/govhub/land/dist/images/equipe/pedro_rossi.jpeg',
        '/govhub/land/dist/images/equipe/victor_suzuki.png'
    ];
    
    console.log('🔄 Iniciando preload das imagens da equipe...');
    
    let loadedCount = 0;
    const totalImages = teamImages.length;
    
    teamImages.forEach(src => {
        const img = new Image();
        
        img.onload = function() {
            loadedCount++;
            console.log(`✅ Imagem carregada: ${src} (${loadedCount}/${totalImages})`);
            
            if (loadedCount === totalImages) {
                console.log('🎉 Todas as imagens da equipe foram carregadas com sucesso!');
            }
        };
        
        img.onerror = function() {
            loadedCount++;
            console.warn(`⚠️ Erro ao carregar imagem: ${src} (${loadedCount}/${totalImages})`);
        };
        
        img.src = src;
    });
}

// Função para inicializar funcionalidades específicas da página Quem Somos
function initQuemSomos() {
    // Preload das imagens quando o DOM estiver carregado
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', preloadTeamImages);
    } else {
        preloadTeamImages();
    }
    
    console.log('👥 Página Quem Somos inicializada com sucesso!');
}

// Inicializar quando o script for carregado
initQuemSomos();

// Exportar função para uso global (se necessário)
window.preloadTeamImages = preloadTeamImages;
