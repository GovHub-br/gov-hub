// Configurar PDF.js
pdfjsLib.GlobalWorkerOptions.workerSrc = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js';

let pdfDoc = null;
let pageNum = 1;
let pageRendering = false;
let pageNumPending = null;
let scale = 1.0; // 100% => página inteira visível (fit-to-contain)
let baseScale = 1.0; // escala base lógica
let canvas, ctx;
let prevBtn, nextBtn, zoomInBtn, zoomOutBtn, pageInfo, zoomLevel, loadingDiv, thumbnailsContainer, toggleSidebarBtn;

const QUALITY_FACTOR = 2.0; // fator extra além do DPR para máxima nitidez
const MAX_DIMENSION = 8192; // limite de segurança por dimensão do canvas

function getViewerAvailableSize() {
    const viewer = document.querySelector('.pdf-viewer');
    if (!viewer) return { width: canvas.parentElement.clientWidth || 800, height: 600 };
    const styles = getComputedStyle(viewer);
    const paddingX = parseFloat(styles.paddingLeft) + parseFloat(styles.paddingRight);
    const paddingY = parseFloat(styles.paddingTop) + parseFloat(styles.paddingBottom);
    const width = Math.max(0, viewer.clientWidth - paddingX);
    const height = Math.max(0, viewer.clientHeight - paddingY);
    return { width, height };
}

// Carregar PDF
function loadPDF() {
    loadingDiv.style.display = 'block';
    
    const pdfUrl = '/govhub/land/dist/ebook/GovHub_Livro-digital_0905.pdf';
    
    pdfjsLib.getDocument(pdfUrl).promise.then(function(pdfDoc_) {
        pdfDoc = pdfDoc_;
        pageInfo.textContent = `Página 1 de ${pdfDoc.numPages}`;
        
        // Atualizar botões
        prevBtn.disabled = pageNum <= 1;
        nextBtn.disabled = pageNum >= pdfDoc.numPages;
        
        loadingDiv.style.display = 'none';
        generateThumbnails();
        renderPage(pageNum);
    }).catch(function(error) {
        console.error('Erro ao carregar PDF:', error);
        loadingDiv.innerHTML = '<p>❌ Erro ao carregar o e-book. <a href="/govhub/land/dist/ebook/GovHub_Livro-digital_0905.pdf" download>Clique aqui para baixar</a></p>';
    });
}

// Renderizar página com alta densidade mantendo a página inteira visível a 100%
function renderPage(num) {
    pageRendering = true;
    
    pdfDoc.getPage(num).then(function(page) {
        const dpr = window.devicePixelRatio || 1;
        const { width: availW, height: availH } = getViewerAvailableSize();

        // Medidas do PDF na escala 1
        const viewportAt1 = page.getViewport({ scale: 1 });

        // Fit-to-contain: usar o menor fator entre largura e altura disponíveis
        const fitScale = Math.min(availW / viewportAt1.width, availH / viewportAt1.height);
        const displayScale = Math.max(0.1, fitScale) * scale; // scale é o multiplicador de zoom

        const displayViewport = page.getViewport({ scale: displayScale });

        // Define tamanho visual (CSS) para caber no container
        canvas.style.width = Math.round(displayViewport.width) + 'px';
        canvas.style.height = Math.round(displayViewport.height) + 'px';

        // Define tamanho real em pixels (render) para alta nitidez
        let renderScale = displayScale * dpr * QUALITY_FACTOR;
        let renderViewport = page.getViewport({ scale: renderScale });

        // Limitar dimensões máximas para evitar estouro de memória/GPU
        if (renderViewport.width > MAX_DIMENSION || renderViewport.height > MAX_DIMENSION) {
            const reduction = Math.min(MAX_DIMENSION / renderViewport.width, MAX_DIMENSION / renderViewport.height);
            renderScale *= reduction;
            renderViewport = page.getViewport({ scale: renderScale });
        }

        canvas.width = Math.floor(renderViewport.width);
        canvas.height = Math.floor(renderViewport.height);

        // Sem transformações CSS (evita borrado)
        canvas.style.transform = '';
        canvas.style.transformOrigin = '';

        if (ctx.imageSmoothingEnabled !== undefined) {
            ctx.imageSmoothingEnabled = false;
        }
        
        const renderContext = {
            canvasContext: ctx,
            viewport: renderViewport
        };
        
        const renderTask = page.render(renderContext);
        
        renderTask.promise.then(function() {
            pageRendering = false;
            if (pageNumPending !== null) {
                renderPage(pageNumPending);
                pageNumPending = null;
            }
        });
    });
    
    pageInfo.textContent = `Página ${num} de ${pdfDoc.numPages}`;
    zoomLevel.textContent = `${Math.round(scale * 100)}%`;
}

// Fila de renderização
function queueRenderPage(num) {
    if (pageRendering) {
        pageNumPending = num;
    } else {
        renderPage(num);
    }
}

// Navegação
function onPrevPage() {
    if (pageNum <= 1) return;
    pageNum--;
    prevBtn.disabled = pageNum <= 1;
    nextBtn.disabled = pageNum >= pdfDoc.numPages;
    queueRenderPage(pageNum);
    updateThumbnailSelection();
}

function onNextPage() {
    if (pageNum >= pdfDoc.numPages) return;
    pageNum++;
    prevBtn.disabled = pageNum <= 1;
    nextBtn.disabled = pageNum >= pdfDoc.numPages;
    queueRenderPage(pageNum);
    updateThumbnailSelection();
}

// Zoom (multiplicador sobre o fit-to-contain)
function onZoomIn() {
    if (scale >= 3.0) return;
    scale += 0.25;
    queueRenderPage(pageNum);
}

function onZoomOut() {
    if (scale <= 0.25) return; // permite ver ainda menor que o fit
    scale -= 0.25;
    queueRenderPage(pageNum);
}

// Gerar miniaturas das páginas
function generateThumbnails() {
    thumbnailsContainer.innerHTML = '';
    
    for (let i = 1; i <= pdfDoc.numPages; i++) {
        const thumbnailDiv = document.createElement('div');
        thumbnailDiv.className = 'pdf-thumbnail';
        thumbnailDiv.dataset.page = i;
        
        const thumbnailCanvas = document.createElement('canvas');
        thumbnailCanvas.className = 'thumbnail-canvas';
        thumbnailDiv.appendChild(thumbnailCanvas);
        
        const pageNumber = document.createElement('div');
        pageNumber.className = 'thumbnail-page-number';
        pageNumber.textContent = i;
        thumbnailDiv.appendChild(pageNumber);
        
        // Renderizar miniatura (DPR limitado para leveza)
        pdfDoc.getPage(i).then(function(page) {
            const dpr = Math.min(1.5, window.devicePixelRatio || 1);
            const cssScale = 0.25;
            const viewportCss = page.getViewport({ scale: cssScale });
            const viewportRender = page.getViewport({ scale: cssScale * dpr });

            thumbnailCanvas.style.width = viewportCss.width + 'px';
            thumbnailCanvas.style.height = viewportCss.height + 'px';
            thumbnailCanvas.width = Math.floor(viewportRender.width);
            thumbnailCanvas.height = Math.floor(viewportRender.height);
            
            const renderContext = {
                canvasContext: thumbnailCanvas.getContext('2d'),
                viewport: viewportRender
            };
            
            page.render(renderContext);
        });
        
        // Adicionar evento de clique
        thumbnailDiv.addEventListener('click', function() {
            pageNum = i;
            prevBtn.disabled = pageNum <= 1;
            nextBtn.disabled = pageNum >= pdfDoc.numPages;
            queueRenderPage(pageNum);
            updateThumbnailSelection();
        });
        
        thumbnailsContainer.appendChild(thumbnailDiv);
    }
    
    updateThumbnailSelection();
}

// Atualizar seleção da miniatura
function updateThumbnailSelection() {
    const thumbnails = document.querySelectorAll('.pdf-thumbnail');
    thumbnails.forEach((thumb, index) => {
        thumb.classList.toggle('active', index + 1 === pageNum);
    });
}

// Toggle sidebar
function toggleSidebar() {
    const sidebar = document.querySelector('.pdf-sidebar');
    const toggleBtn = document.getElementById('toggleSidebar');
    const icon = toggleBtn.querySelector('i');
    
    sidebar.classList.toggle('collapsed');
    
    if (sidebar.classList.contains('collapsed')) {
        icon.className = 'fas fa-chevron-right';
    } else {
        icon.className = 'fas fa-chevron-left';
    }

    // Recalcular ajuste após colapsar/expandir
    if (pdfDoc) queueRenderPage(pageNum);
}

// PDF Fullscreen toggle
function toggleFullscreen() {
    const pdfViewer = document.querySelector('.pdf-viewer');
    if (!document.fullscreenElement) {
        pdfViewer.requestFullscreen().catch(err => {
            console.log('Erro ao entrar em tela cheia:', err);
        });
    } else {
        document.exitFullscreen();
    }
}

document.addEventListener('fullscreenchange', () => {
    if (pdfDoc) queueRenderPage(pageNum);
});

// Navegação por teclado
document.addEventListener('keydown', function(e) {
    if (e.key === 'ArrowLeft') onPrevPage();
    if (e.key === 'ArrowRight') onNextPage();
    if (e.key === '+' || e.key === '=') onZoomIn();
    if (e.key === '-') onZoomOut();
});

// Re-render ao redimensionar para manter ajuste e nitidez
addEventListener('resize', () => {
    if (pdfDoc) queueRenderPage(pageNum);
});

// Inicializar quando a página estiver pronta
document.addEventListener('DOMContentLoaded', function() {
    // Inicializar elementos do DOM
    canvas = document.getElementById('pdfCanvas');
    ctx = canvas.getContext('2d');
    
    // Elementos da interface
    prevBtn = document.getElementById('prevPage');
    nextBtn = document.getElementById('nextPage');
    zoomInBtn = document.getElementById('zoomIn');
    zoomOutBtn = document.getElementById('zoomOut');
    pageInfo = document.getElementById('pageInfo');
    zoomLevel = document.getElementById('zoomLevel');
    loadingDiv = document.querySelector('.pdf-loading');
    thumbnailsContainer = document.getElementById('pdfThumbnails');
    toggleSidebarBtn = document.getElementById('toggleSidebar');
    
    // Event listeners
    prevBtn.addEventListener('click', onPrevPage);
    nextBtn.addEventListener('click', onNextPage);
    zoomInBtn.addEventListener('click', onZoomIn);
    zoomOutBtn.addEventListener('click', onZoomOut);
    toggleSidebarBtn.addEventListener('click', toggleSidebar);
    
    // Carregar PDF
    loadPDF();
    
});
