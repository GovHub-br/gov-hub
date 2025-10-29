// ========================================
// DASHBOARD DE PESSOAS - JAVASCRIPT FILE
// ========================================

// Dados mockados para o gráfico de raça/cor
const raceData = [
    { name: 'BRANCA', value: 250 },
    { name: 'PARDA', value: 72 },
    { name: 'PRETA', value: 25 },
    { name: 'AMARELA', value: 8 },
    { name: 'INDÍGENA', value: 3 },
    { name: 'NÃO DECLARADA', value: 2 }
];

// Mapeamento de cores para cada raça/cor (seguindo o padrão da página dashboards)
const colorMap = {
    'BRANCA': '#FF8C00',
    'PARDA': '#FFA500', 
    'PRETA': '#8A2BE2',
    'AMARELA': '#9370DB',
    'INDÍGENA': '#9932CC',
    'NÃO DECLARADA': '#DDA0DD'
};

// Função para criar o gráfico de raça/cor (treemap)
function createRaceTreemap() {
    const chartDom = document.getElementById('raceChart');
    if (!chartDom) return;
    
    const myChart = echarts.init(chartDom);
    
    // Mapear dados para o formato do ECharts
    const chartData = raceData.map(item => ({
        name: item.name,
        value: item.value,
        itemStyle: { 
            color: colorMap[item.name] || '#DDA0DD',
            borderColor: '#ffffff',
            borderWidth: 2
        }
    })).sort((a, b) => b.value - a.value); // Ordenar por valor decrescente

    const option = {
        backgroundColor: 'transparent',
        tooltip: {
            trigger: 'item',
            backgroundColor: '#422278',
            borderColor: '#7A34F3',
            borderWidth: 1,
            textStyle: {
                color: '#ffffff',
                fontFamily: 'Inter'
            },
            formatter: function(params) {
                return params.name + '<br/>' + params.value + ' funcionários';
            }
        },
        series: [
            {
                type: 'treemap',
                data: chartData,
                roam: false,
                nodeClick: false,
                breadcrumb: {
                    show: false
                },
                label: {
                    show: true,
                    formatter: function(params) {
                        // Mostrar apenas para os blocos individuais, não para o total
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
                upperLabel: {
                    show: false
                },
                itemStyle: {
                    borderColor: '#ffffff',
                    borderWidth: 2,
                    gapWidth: 2
                },
                emphasis: {
                    itemStyle: {
                        borderColor: '#7A34F3',
                        borderWidth: 3
                    }
                }
            }
        ]
    };

    myChart.setOption(option);

    // Responsividade
    window.addEventListener('resize', function() {
        myChart.resize();
    });

    return myChart;
}

// Função para inicializar todos os gráficos
function initializeCharts() {
    console.log('🚀 Inicializando gráficos do dashboard de pessoas...');
    
    // Criar gráfico de raça/cor
    createRaceTreemap();
    
    console.log('✅ Gráficos inicializados com sucesso!');
}

// Função para animar as barras do gráfico de gênero
function animateGenderBars() {
    const bars = document.querySelectorAll('.bar-fill:not(.functional-bar)');
    
    bars.forEach((bar, index) => {
        setTimeout(() => {
            // Obter a largura atual do elemento (do CSS ou style inline)
            const computedStyle = window.getComputedStyle(bar);
            const currentWidth = computedStyle.width;
            
            bar.style.transition = 'width 1s ease-out';
            bar.style.width = '0%';
            
            setTimeout(() => {
                bar.style.width = currentWidth;
            }, 100);
        }, index * 200);
    });
}

// Função para animar as barras do gráfico de situação funcional
function animateFunctionalBars() {
    const functionalBars = document.querySelectorAll('.functional-situation-chart .bar-fill');
    
    functionalBars.forEach((bar, index) => {
        setTimeout(() => {
            // Obter a largura atual do elemento (do CSS ou style inline)
            const computedStyle = window.getComputedStyle(bar);
            const currentWidth = computedStyle.width;
            
            bar.style.transition = 'width 1.2s ease-out';
            bar.style.width = '0%';
            
            setTimeout(() => {
                bar.style.width = currentWidth;
            }, 150);
        }, index * 300);
    });
}

// Função para controlar os botões All/Inv do gráfico de gênero
function setupGenderControls() {
    const controlBtns = document.querySelectorAll('.control-btn');
    
    controlBtns.forEach(btn => {
        btn.addEventListener('click', function() {
            // Remover classe active de todos os botões
            controlBtns.forEach(b => b.classList.remove('active'));
            
            // Adicionar classe active ao botão clicado
            this.classList.add('active');
            
            // TODO: Adicionar lógica para filtrar os dados quando necessário
        });
    });
}

// Função para adicionar hover effects aos cards
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

// Função para animar os valores dos KPIs
function animateKPIs() {
    const kpiValues = document.querySelectorAll('.budget-value');
    
    kpiValues.forEach((element, index) => {
        const finalValue = element.textContent;
        const isKValue = finalValue.includes('k');
        const numericValue = parseFloat(finalValue.replace('k', ''));
        
        element.textContent = '0';
        
        setTimeout(() => {
            let currentValue = 0;
            const increment = numericValue / 50; // 50 steps para a animação
            
            const timer = setInterval(() => {
                currentValue += increment;
                
                if (currentValue >= numericValue) {
                    element.textContent = finalValue;
                    clearInterval(timer);
                } else {
                    const displayValue = Math.floor(currentValue);
                    element.textContent = isKValue ? displayValue + 'k' : displayValue.toString();
                }
            }, 20);
        }, index * 200);
    });
}

// Função principal de inicialização
function initDashboard() {
    console.log('🎯 Inicializando Dashboard de Pessoas...');
    
    // Aguardar o DOM estar pronto
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function() {
            initializeDashboard();
        });
    } else {
        initializeDashboard();
    }
}

function initializeDashboard() {
    try {
        // Inicializar gráficos
        initializeCharts();
        
        // Configurar controles
        setupGenderControls();
        
        // Configurar efeitos visuais
        setupCardHoverEffects();
        
        // Animar elementos
        setTimeout(() => {
            animateKPIs();
            animateGenderBars();
            animateFunctionalBars();
        }, 500);
        
        console.log('✅ Dashboard de Pessoas inicializado com sucesso!');
        
    } catch (error) {
        console.error('❌ Erro ao inicializar dashboard:', error);
    }
}

// Dados do mapa do Brasil com porcentagens aleatórias
const brazilMapData = {
    'RJ': { name: 'RIO DE JANEIRO', value: 0, percentage: '0%' },
    'SP': { name: 'SÃO PAULO', value: 45, percentage: '45%' },
    'MG': { name: 'MINAS GERAIS', value: 32, percentage: '32%' },
    'RS': { name: 'RIO GRANDE DO SUL', value: 28, percentage: '28%' },
    'PR': { name: 'PARANÁ', value: 15, percentage: '15%' },
    'SC': { name: 'SANTA CATARINA', value: 22, percentage: '22%' },
    'BA': { name: 'BAHIA', value: 38, percentage: '38%' },
    'GO': { name: 'GOIÁS', value: 12, percentage: '12%' },
    'DF': { name: 'DISTRITO FEDERAL', value: 80, percentage: '80%' },
    'CE': { name: 'CEARÁ', value: 8, percentage: '8%' },
    'PE': { name: 'PERNAMBUCO', value: 18, percentage: '18%' },
    'PA': { name: 'PARÁ', value: 5, percentage: '5%' },
    'AM': { name: 'AMAZONAS', value: 3, percentage: '3%' },
    'AC': { name: 'ACRE', value: 2, percentage: '2%' },
    'RO': { name: 'RONDÔNIA', value: 4, percentage: '4%' },
    'RR': { name: 'RORAIMA', value: 1, percentage: '1%' },
    'AP': { name: 'AMAPÁ', value: 2, percentage: '2%' },
    'TO': { name: 'TOCANTINS', value: 6, percentage: '6%' },
    'MT': { name: 'MATO GROSSO', value: 9, percentage: '9%' },
    'MS': { name: 'MATO GROSSO DO SUL', value: 7, percentage: '7%' },
    'ES': { name: 'ESPÍRITO SANTO', value: 25, percentage: '25%' },
    'AL': { name: 'ALAGOAS', value: 14, percentage: '14%' },
    'SE': { name: 'SERGIPE', value: 11, percentage: '11%' },
    'PB': { name: 'PARAÍBA', value: 16, percentage: '16%' },
    'RN': { name: 'RIO GRANDE DO NORTE', value: 13, percentage: '13%' },
    'MA': { name: 'MARANHÃO', value: 4, percentage: '4%' },
    'PI': { name: 'PIAUÍ', value: 6, percentage: '6%' }
};


// Função para carregar o SVG do mapa do Brasil
function loadBrazilMap() {
    const mapContainer = document.getElementById('brazilMap');
    if (!mapContainer) return;

    // Carregar o SVG
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

// Função para inicializar a interatividade do mapa
function initializeMapInteractivity() {
    const mapContainer = document.getElementById('brazilMap');
    const svg = mapContainer.querySelector('svg');
    if (!svg) return;

    // Criar tooltip
    const tooltip = document.createElement('div');
    tooltip.className = 'map-tooltip';
    mapContainer.appendChild(tooltip);

    // Aplicar dados aos estados
    const paths = svg.querySelectorAll('path');
    
    // Função auxiliar para atualizar posição do tooltip
    const updateTooltipPosition = (e, tooltip) => {
        const rect = mapContainer.getBoundingClientRect();
        tooltip.style.left = (e.clientX - rect.left) + 'px';
        tooltip.style.top = (e.clientY - rect.top - 40) + 'px';
    };
    
    paths.forEach((path) => {
        // Obter e normalizar o ID do path
        let stateId = path.getAttribute('id');
        if (stateId) {
            stateId = stateId.toUpperCase().trim();
        }
        
        // Verificar se temos dados para este estado
        const data = brazilMapData[stateId];
        const tooltipText = data 
            ? `${data.name} ${data.percentage}` 
            : stateId || 'Estado';

        // Adicionar eventos de hover (unificados para todos os estados)
        path.addEventListener('mouseenter', function(e) {
            tooltip.textContent = tooltipText;
            updateTooltipPosition(e, tooltip);
            tooltip.classList.add('show');
        });

        path.addEventListener('mouseleave', function() {
            tooltip.classList.remove('show');
        });

        path.addEventListener('mousemove', function(e) {
            if (tooltip.classList.contains('show')) {
                updateTooltipPosition(e, tooltip);
            }
        });
    });
}

// Inicializar o dashboard
initDashboard();

// Carregar o mapa do Brasil
loadBrazilMap();
