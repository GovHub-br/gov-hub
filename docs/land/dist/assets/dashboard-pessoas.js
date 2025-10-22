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
    const bars = document.querySelectorAll('.bar-fill');
    
    bars.forEach((bar, index) => {
        setTimeout(() => {
            bar.style.transition = 'width 1s ease-out';
            const width = bar.style.width;
            bar.style.width = '0%';
            
            setTimeout(() => {
                bar.style.width = width;
            }, 100);
        }, index * 200);
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
            
            // Aqui você pode adicionar lógica para filtrar os dados
            console.log('Filtro selecionado:', this.textContent);
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

// Função para setup de responsividade
function setupResponsiveCharts() {
    const raceChart = echarts.getInstanceByDom(document.getElementById('raceChart'));
    
    window.addEventListener('resize', function() {
        if (raceChart) {
            raceChart.resize();
        }
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
        }, 500);
        
        // Configurar responsividade
        setupResponsiveCharts();
        
        console.log('✅ Dashboard de Pessoas inicializado com sucesso!');
        
    } catch (error) {
        console.error('❌ Erro ao inicializar dashboard:', error);
    }
}

// Inicializar o dashboard
initDashboard();
