# E-book: Gov Hub - Plataforma Livre de Integração de Dados

<div class="pdf-viewer-container">
  <div class="pdf-viewer">
    <canvas id="pdfCanvas"></canvas>
  </div>
  
  <div class="pdf-controls">
    <button id="prevPage" class="pdf-btn" disabled>← Página Anterior</button>
    <span id="pageInfo" class="page-info">Página 1 de 1</span>
    <button id="nextPage" class="pdf-btn" disabled>Próxima Página →</button>
    <button id="zoomOut" class="pdf-btn">🔍-</button>
    <span id="zoomLevel" class="zoom-info">100%</span>
    <button id="zoomIn" class="pdf-btn">🔍+</button>
    <a href="/govhub/land/dist/ebook/GovHub_Livro-digital_0905.pdf" download class="pdf-btn download-btn">Baixar PDF</a>
  </div>
  
  <div class="pdf-loading">
    <div class="loading-spinner"></div>
    <p>Carregando e-book...</p>
  </div>
</div>

<script src="https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.min.js"></script>
<script>
// Configurar PDF.js
pdfjsLib.GlobalWorkerOptions.workerSrc = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js';

let pdfDoc = null;
let pageNum = 1;
let pageRendering = false;
let pageNumPending = null;
let scale = 1.0;
const canvas = document.getElementById('pdfCanvas');
const ctx = canvas.getContext('2d');

// Elementos da interface
const prevBtn = document.getElementById('prevPage');
const nextBtn = document.getElementById('nextPage');
const zoomInBtn = document.getElementById('zoomIn');
const zoomOutBtn = document.getElementById('zoomOut');
const pageInfo = document.getElementById('pageInfo');
const zoomLevel = document.getElementById('zoomLevel');
const loadingDiv = document.querySelector('.pdf-loading');

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
    renderPage(pageNum);
  }).catch(function(error) {
    console.error('Erro ao carregar PDF:', error);
    loadingDiv.innerHTML = '<p>❌ Erro ao carregar o e-book. <a href="/govhub/land/dist/ebook/GovHub_Livro-digital_0905.pdf" download>Clique aqui para baixar</a></p>';
  });
}

// Renderizar página
function renderPage(num) {
  pageRendering = true;
  
  pdfDoc.getPage(num).then(function(page) {
    const viewport = page.getViewport({scale: scale});
    canvas.height = viewport.height;
    canvas.width = viewport.width;
    
    const renderContext = {
      canvasContext: ctx,
      viewport: viewport
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
}

function onNextPage() {
  if (pageNum >= pdfDoc.numPages) return;
  pageNum++;
  prevBtn.disabled = pageNum <= 1;
  nextBtn.disabled = pageNum >= pdfDoc.numPages;
  queueRenderPage(pageNum);
}

// Zoom
function onZoomIn() {
  if (scale >= 3.0) return;
  scale += 0.25;
  queueRenderPage(pageNum);
}

function onZoomOut() {
  if (scale <= 0.5) return;
  scale -= 0.25;
  queueRenderPage(pageNum);
}

// Event listeners
prevBtn.addEventListener('click', onPrevPage);
nextBtn.addEventListener('click', onNextPage);
zoomInBtn.addEventListener('click', onZoomIn);
zoomOutBtn.addEventListener('click', onZoomOut);

// Navegação por teclado
document.addEventListener('keydown', function(e) {
  if (e.key === 'ArrowLeft') onPrevPage();
  if (e.key === 'ArrowRight') onNextPage();
  if (e.key === '+' || e.key === '=') onZoomIn();
  if (e.key === '-') onZoomOut();
});

// Carregar PDF quando a página estiver pronta
document.addEventListener('DOMContentLoaded', loadPDF);
</script>

