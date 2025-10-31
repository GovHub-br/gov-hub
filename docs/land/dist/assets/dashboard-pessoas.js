// ========================================
// DASHBOARD DE PESSOAS - JAVASCRIPT FILE
// ========================================

const PESSOAS_DATA_PATHS = [
    '../public/data/pessoas_visao_geral.json'
];

// Cores para raça/cor
const colorMap = {
    'BRANCA': '#FF8C00',
    'PARDA': '#FFA500', 
    'PRETA': '#8A2BE2',
    'AMARELA': '#9370DB',
    'INDÍGENA': '#9932CC',
    'NÃO DECLARADA': '#DDA0DD',
    'NAO INFORMADO': '#DDA0DD'
};

async function fetchPessoasData() {
    for (const basePath of PESSOAS_DATA_PATHS) {
        try {
            const urlWithBust = `${basePath}?v=${Date.now()}`;
            const resp = await fetch(urlWithBust, { cache: 'no-store' });
            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
            return await resp.json();
        } catch (e) {
            // tenta próximo caminho
        }
    }
    const hdr = document.querySelector('.header-date');
    if (hdr) hdr.textContent = 'Erro ao carregar dados';
    console.error('Não foi possível carregar pessoas_visao_geral.json');
    return null;
}

function setHeaderDateFromData(data) {
    const el = document.querySelector('.header-date');
    if (!el || !data || !data.meta || !data.meta.atualizado_em) return;
    el.textContent = data.meta.atualizado_em;
}

function setKpisFromData(data) {
    if (!data || !data.kpis) return;
    const { total_servidores, servidores_ativos_permanentes, aposentados, estagiarios } = data.kpis;

    const idMap = [
        ['kpi-total-servidores', total_servidores],
        ['kpi-ativos-permanentes', servidores_ativos_permanentes],
        ['kpi-aposentados', aposentados],
        ['kpi-estagiarios', estagiarios]
    ];
    let appliedById = 0;
    idMap.forEach(([id, value]) => {
        const el = document.getElementById(id);
        if (el) {
            el.textContent = formatKpi(Number(value) || 0);
            appliedById++;
        }
    });

    if (appliedById === idMap.length) return;

    const cards = Array.from(document.querySelectorAll('.budget-card'));
    cards.forEach(card => {
        const title = card.querySelector('.budget-card-title');
        const valueEl = card.querySelector('.budget-value');
        if (!title || !valueEl) return;
        const t = (title.textContent || '').toUpperCase();
        if (t.includes('TOTAL DE SERVIDORES')) valueEl.textContent = formatKpi(total_servidores);
        else if (t.includes('SERVIDORES ATIVOS PERMANENTES')) valueEl.textContent = formatKpi(servidores_ativos_permanentes);
        else if (t.includes('APOSENTADOS')) valueEl.textContent = formatKpi(aposentados);
        else if (t.includes('ESTAGIÁRIOS')) valueEl.textContent = formatKpi(estagiarios);
    });
}

function formatKpi(n) {
    if (n >= 1000) {
        const k = (n / 1000);
        return (Math.round(k * 100) / 100) + 'k';
    }
    return String(n);
}

function setGeneroFromData(data) {
    if (!data || !data.genero) return;
    const fem = Number(data.genero.feminino_percent) || 0;
    const masc = Number(data.genero.masculino_percent) || 0;

    const barItems = document.querySelectorAll('.chart-card .bars-container .bar-item');
    barItems.forEach(item => {
        const label = (item.querySelector('.bar-label')?.textContent || '').trim().toUpperCase();
        const fill = item.querySelector('.bar-fill');
        const value = item.querySelector('.bar-value');
        if (!fill || !value) return;
        if (label.includes('FEMININO')) {
            fill.style.width = fem + '%';
            value.textContent = fem.toFixed(1) + '%';
        } else if (label.includes('MASCULINO')) {
            fill.style.width = masc + '%';
            value.textContent = masc.toFixed(1) + '%';
        }
    });
}

function createRaceTreemapFromData(data) {
    const chartDom = document.getElementById('raceChart');
    if (!chartDom) return;
    if (!data || !Array.isArray(data.raca_cor) || data.raca_cor.length === 0) {
        chartDom.innerHTML = '<div style="color:#b91c1c;font-size:12px;">Sem dados de raça/cor</div>';
        return;
    }

    const myChart = echarts.init(chartDom);
    const mapped = data.raca_cor.map(item => ({
        name: item.nome_cor,
        value: item.valor,
        itemStyle: { 
            color: colorMap[item.nome_cor] || '#DDA0DD',
            borderColor: '#ffffff',
            borderWidth: 2
        }
    })).sort((a, b) => b.value - a.value);

    const option = {
        backgroundColor: 'transparent',
        tooltip: {
            trigger: 'item',
            backgroundColor: '#422278',
            borderColor: '#7A34F3',
            borderWidth: 1,
            textStyle: { color: '#ffffff', fontFamily: 'Inter' },
            formatter: function(params) { return params.name + '<br/>' + params.value + ' funcionários'; }
        },
        series: [
            {
                type: 'treemap',
                data: mapped,
                roam: false,
                nodeClick: false,
                breadcrumb: { show: false },
                label: {
                    show: true,
                    formatter: function(params) {
                        if (params.treePathInfo && params.treePathInfo.length > 1) {
                            return params.name + '\n' + params.value;
                        }
                        return '';
                    },
                    fontSize: 12,
                    fontWeight: 'bold',
                    color: '#ffffff',
                    textShadowColor: 'rgba(0, 0, 0, 0.5)',
                    textShadowBlur: 2
                },
                upperLabel: { show: false },
                itemStyle: { borderColor: '#ffffff', borderWidth: 2, gapWidth: 2 },
                emphasis: { itemStyle: { borderColor: '#7A34F3', borderWidth: 3 } }
            }
        ]
    };

    myChart.setOption(option);
    window.addEventListener('resize', function() { myChart.resize(); });
    return myChart;
}

function setSituacaoFuncionalFromData(data) {
    if (!data || !Array.isArray(data.situacao_funcional)) return;
    const items = data.situacao_funcional;
    const maxValor = Math.max(...items.map(i => i.valor || 0), 1);

    const containerItems = document.querySelectorAll('.functional-situation-chart .bar-item');
    containerItems.forEach(ci => {
        const labelEl = ci.querySelector('.bar-label');
        const valueEl = ci.querySelector('.bar-value');
        const fillEl = ci.querySelector('.bar-fill');
        if (!labelEl || !valueEl || !fillEl) return;
        const label = (labelEl.textContent || '').trim();
        const found = items.find(i => (i.label || '').trim() === label);
        if (found) {
            valueEl.textContent = String(found.valor);
            const percent = (found.valor / maxValor) * 100;
            fillEl.style.width = percent.toFixed(1) + '%';
        }
    });
}

function setupGenderControls() {
    const controlBtns = document.querySelectorAll('.control-btn');
    controlBtns.forEach(btn => {
        btn.addEventListener('click', function() {
            controlBtns.forEach(b => b.classList.remove('active'));
            this.classList.add('active');
        });
    });
}

function setupCardHoverEffects() {
    const cards = document.querySelectorAll('.chart-card, .budget-card');
    cards.forEach(card => {
        card.addEventListener('mouseenter', function() {
            this.style.transform = 'translateY(-2px)';
            this.style.boxShadow = '0 8px 25px rgba(0, 0, 0, 0.1)';
        });
        card.addEventListener('mouseleave', function() {
            this.style.transform = 'translateY(0)';
            this.style.boxShadow = '0 2px 4px rgba(0, 0, 0, 0.05)';
        });
    });
}

function animateKPIs() {
    const kpiValues = document.querySelectorAll('.budget-value');
    kpiValues.forEach((element, index) => {
        const finalValue = element.textContent;
        const isKValue = finalValue.includes('k');
        const numericValue = parseFloat(finalValue.replace('k', '')) || 0;
        element.textContent = '0';
        setTimeout(() => {
            let currentValue = 0;
            const steps = 50;
            const increment = numericValue / steps;
            const timer = setInterval(() => {
                currentValue += increment;
                if (currentValue >= numericValue) {
                    element.textContent = finalValue;
                    clearInterval(timer);
                } else {
                    const displayValue = Math.floor(currentValue * 100) / 100;
                    element.textContent = isKValue ? displayValue + 'k' : displayValue.toString();
                }
            }, 20);
        }, index * 200);
    });
}

function overrideBrazilMapDataFromJson(data) {
    if (!data || !data.mapa_uf) return;
    const src = data.mapa_uf;
    Object.keys(src).forEach(uf => {
        const it = src[uf];
        brazilMapData[uf] = {
            name: it.nome || it.name || uf,
            value: it.valor || it.value || 0,
            percentage: it.percentual || it.percentage || '0%'
        };
    });
}

function loadBrazilMap() {
    const mapContainer = document.getElementById('brazilMap');
    if (!mapContainer) return;

    fetch('./images/Map-Brasil.svg')
        .then(response => response.text())
        .then(svgText => {
            mapContainer.innerHTML = svgText;
            initializeMapInteractivity();
        })
        .catch(error => {
            console.error('Erro ao carregar o mapa do Brasil:', error);
            mapContainer.innerHTML = '<p>Erro ao carregar o mapa</p>';
        });
}

function initializeMapInteractivity() {
    const mapContainer = document.getElementById('brazilMap');
    const svg = mapContainer.querySelector('svg');
    if (!svg) return;

    const tooltip = document.createElement('div');
    tooltip.className = 'map-tooltip';
    mapContainer.appendChild(tooltip);

    const paths = svg.querySelectorAll('path');
    const updateTooltipPosition = (e, tooltip) => {
        const rect = mapContainer.getBoundingClientRect();
        tooltip.style.left = (e.clientX - rect.left) + 'px';
        tooltip.style.top = (e.clientY - rect.top - 40) + 'px';
    };
    
    paths.forEach((path) => {
        let stateId = path.getAttribute('id');
        if (stateId) stateId = stateId.toUpperCase().trim();
        const data = brazilMapData[stateId];
        const tooltipText = data ? `${data.name} ${data.percentage}` : stateId || 'Estado';
        path.addEventListener('mouseenter', function(e) {
            tooltip.textContent = tooltipText;
            updateTooltipPosition(e, tooltip);
            tooltip.classList.add('show');
        });
        path.addEventListener('mouseleave', function() { tooltip.classList.remove('show'); });
        path.addEventListener('mousemove', function(e) { if (tooltip.classList.contains('show')) updateTooltipPosition(e, tooltip); });
    });
}

async function populateServidoresTableFromData(data) {
    const tbody = document.getElementById('servidoresTableBody');
    if (!tbody) return;
    if (!data || !Array.isArray(data.tabela_servidores)) {
        tbody.innerHTML = '';
        return;
    }
    tbody.innerHTML = '';
    data.tabela_servidores.forEach(row => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td>${row.cargo}</td>
            <td>${row.genero}</td>
            <td>${row.situacao}</td>
            <td>${row.cidade}</td>
            <td>${row.estado}</td>
            <td>${row.total}</td>
        `;
        tbody.appendChild(tr);
    });
}

function setupServidoresSearch() {
    const searchWrapper = document.getElementById('servidoresSearchWrapper');
    const searchInput = document.getElementById('servidoresSearchInput');
    const tableBody = document.getElementById('servidoresTableBody');
    if (!searchWrapper || !searchInput || !tableBody) return;
    searchWrapper.addEventListener('click', function(e) {
        if (e.target === searchInput) return;
        searchWrapper.classList.toggle('active');
        if (searchWrapper.classList.contains('active')) setTimeout(() => { searchInput.focus(); }, 100);
    });
    searchInput.addEventListener('click', function(e) { e.stopPropagation(); });
    document.addEventListener('click', function(e) { if (!searchWrapper.contains(e.target)) searchWrapper.classList.remove('active'); });
    searchInput.addEventListener('input', function(e) {
        const searchTerm = e.target.value.toLowerCase().trim();
        const rows = tableBody.querySelectorAll('tr');
        rows.forEach(row => {
            const cells = row.querySelectorAll('td');
            let found = false;
            cells.forEach(cell => { if (cell.textContent.toLowerCase().includes(searchTerm)) found = true; });
            row.style.display = (found || searchTerm === '') ? '' : 'none';
        });
    });
}

function initDashboard() {
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function() { initializeDashboard(); });
    } else {
        initializeDashboard();
    }
}

async function initializeDashboard() {
    try {
        const data = await fetchPessoasData();
        if (data) {
            setHeaderDateFromData(data);
            setKpisFromData(data);
            setGeneroFromData(data);
            createRaceTreemapFromData(data);
            setSituacaoFuncionalFromData(data);
            overrideBrazilMapDataFromJson(data);
        }

        loadBrazilMap();
        await populateServidoresTableFromData(data);
        setupGenderControls();
        setupCardHoverEffects();
        setTimeout(() => { animateKPIs(); animateGenderBars(); animateFunctionalBars(); }, 500);
    } catch (error) {
        console.error('Erro ao inicializar dashboard:', error);
    }
}

const brazilMapData = {};

initDashboard();

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function() { setupServidoresSearch(); });
} else {
    setupServidoresSearch();
}
