// ========================================
// DASHBOARDS PAGE - JAVASCRIPT FILE
// ========================================

// Função para criar o gráfico de rosca
function createBudgetChart() {
    const ctx = document.getElementById('budgetChart');
    if (!ctx) return;

    const palette = ['#AB2D2D', '#E24747', '#FB8585', '#31652B', '#67A95E', '#AFD1AA', '#422278', '#326879', '#8B4513', '#F59E0B', '#22c55e'];

    function formatMillions(value) {
        const m = value / 1_000_000;
        return m.toFixed(1).replace('.', ',') + 'M';
    }

    function updateBudgetLegend(labels, values) {
        const chartCard = ctx.closest('.chart-card');
        if (!chartCard) return;
        const legend = chartCard.querySelector('.chart-legend');
        if (!legend) return;

        const legendItems = Array.from(legend.querySelectorAll('.legend-item'));
        const count = Math.min(legendItems.length, labels.length, values.length);

        for (let i = 0; i < count; i++) {
            const item = legendItems[i];
            const textEl = item.querySelector('.legend-text');
            if (!textEl) continue;
            const formatted = formatMillions(values[i]);
            const fullLabel = labels[i] || '';
            const limit = 45;
            const truncated = fullLabel.length > limit ? `${fullLabel.slice(0, limit)}…` : fullLabel;
            textEl.innerHTML = `<span class="legend-number">${formatted}</span> ${truncated}`;
            textEl.classList.add('has-tooltip');
            textEl.setAttribute('data-full', fullLabel);
        }
    }

    function renderChart(labels, values) {
        const backgroundColor = palette.slice(0, labels.length);
        const chartData = {
            labels: labels,
            datasets: [{
                data: values.map(v => v / 1_000_000),
                backgroundColor: backgroundColor,
                borderWidth: 0,
                cutout: '60%'
            }]
        };

        const config = {
            type: 'doughnut',
            data: chartData,
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: getTooltipConfig('Distribuição de Orçamento')
                },
                elements: { arc: { borderWidth: 0 } }
            }
        };

        new Chart(ctx, config);

        const totalMillions = values.reduce((sum, v) => sum + (v / 1_000_000), 0);
        updateChartTotal('budgetChart', Math.round(totalMillions));

        updateBudgetLegend(labels, values);
    }

    const dataUrl = '../public/data/orcamento_por_acao.json';
    const urlWithBust = `${dataUrl}?v=${Date.now()}`;

    fetch(urlWithBust, { cache: 'no-store' })
        .then(resp => {
            if (!resp.ok) throw new Error('fetch not ok');
            return resp.json();
        })
        .then(json => {
            const labels = json.map(item => item.descricao);
            const values = json.map(item => Number(item.valor) || 0);
            renderChart(labels, values);
        })
        .catch(() => {
            const labels = [
                'Ativos civis da união',
                'Aposentadorias e pensões civis da união',
                'Administração da unidade',
                'Contribuição da união de suas autarquias e fundações para o',
                'Concessão de bolsas para pesquisa economica',
                'Benefícios obrigatorios aos servidores civis, empregados, mi',
                'Exercício da presidência dos Brics pelo brasil',
                'Assistencia medica e odontologica aos servidores civis, empr...'
            ];
            const values = [262_000_000, 253_000_000, 73_200_000, 44_600_000, 8_870_000, 3_740_000, 2_380_000, 2_280_000];
            renderChart(labels, values);
        });
}

// Função para inicializar funcionalidades específicas da página de dashboards
function initDashboards() {
    // Criar o gráfico quando o DOM estiver carregado
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', createBudgetChart);
    } else {
        createBudgetChart();
    }
    
    console.log('📊 Página Dashboards inicializada com sucesso!');
}

// Função para atualizar o total do gráfico
function updateChartTotal(chartId, totalValue) {
    const totalElement = document.querySelector(`#${chartId}`).parentElement.querySelector('.chart-total-number');
    if (totalElement) {
        totalElement.textContent = totalValue + 'M';
    }
}

// Função para criar configuração padrão de tooltip
function getTooltipConfig(title) {
    return {
        backgroundColor: '#422278',
        titleColor: '#FFFFFF',
        bodyColor: '#FFFFFF',
        padding: 16,
        cornerRadius: 8,
        displayColors: true,
        borderColor: '#7A34F3',
        borderWidth: 1,
        titleFont: {
            size: 14,
            weight: '600',
            family: 'Inter'
        },
        bodyFont: {
            size: 13,
            weight: '400',
            family: 'Inter'
        },
        callbacks: {
            title: function(context) {
                return title;
            },
            label: function(context) {
                const value = context.parsed;
                if (typeof value === 'number') {
                    return 'Valor: ' + value.toLocaleString('pt-BR') + 'M';
                }
                return 'Valor: ' + value;
            }
        }
    };
}

// Carregar KPIs orçamentários a partir do JSON público
function loadBudgetKpis() {
    const dataUrl = '../public/data/visao_orcamentaria_total_ipea.json';
    const urlWithBust = `${dataUrl}?v=${Date.now()}`;

    function formatMillions(value) {
        const millions = (Number(value) || 0) / 1_000_000;
        return millions.toFixed(1).replace('.', ',') + 'M';
    }

    function setValue(id, value) {
        const el = document.getElementById(id);
        if (el) {
            el.textContent = formatMillions(value);
        }
    }

    fetch(urlWithBust, { cache: 'no-store' })
        .then(resp => {
            if (!resp.ok) throw new Error('fetch not ok');
            return resp.json();
        })
        .then(json => {
            const row = Array.isArray(json) ? json[0] : json;
            if (!row) return;
            setValue('total-budget', row.orcamento_total);
            setValue('teds-budget', row.orcamento_recebido_teds);
            setValue('agency-budget', row.dotacao_atualizada);
            setValue('allocated-budget', row.orcamento_empenhado);
            setValue('unused-budget', row.orcamento_a_liquidar);
            setValue('programmed-expenses', row.despesas_a_pagar);
            setValue('paid-expenses', row.despesas_pagas);
        })
        .catch(() => {
            // mantém valores existentes se falhar
        });
}


// Função para criar os gráficos de dashboard
function createDashboardCharts() {
    // Gráfico 1 - Aposentadorias, Reserva Remunerada e Reformas
    const retirementCtx = document.getElementById('retirementChart');
    if (retirementCtx) {
        // Dados do gráfico
        const retirementData = [
            { filled: 67, empty: 30 }, // Anel externo
            { filled: 67, empty: 30 },   // Anel médio
            { filled: 68, empty: 30 }    // Anel interno
        ];
        
        // Calcular total (soma dos valores preenchidos)
        const retirementTotal = retirementData.reduce((sum, ring) => sum + ring.filled, 0);
        
        new Chart(retirementCtx, {
            type: 'doughnut',
            data: {
                datasets: [
                    {
                        data: [retirementData[0].filled, retirementData[0].empty],
                        backgroundColor: ['#AA79FE', '#F7F7F7'],
                        borderWidth: 1,
                        borderColor: '#F7F7F7',
                        cutout: '60%'
                    },
                    {
                        data: [retirementData[1].filled, retirementData[1].empty],
                        backgroundColor: ['#7A34F3', '#F7F7F7'],
                        borderWidth: 1,
                        borderColor: '#F7F7F7',
                        cutout: '60%'
                    },
                    {
                        data: [retirementData[2].filled, retirementData[2].empty],
                        backgroundColor: ['#422278', '#F7F7F7'],
                        borderWidth: 1,
                        borderColor: '#F7F7F7',
                        cutout: '60%'
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: getTooltipConfig('Aposentadorias e Reformas')
                }
            }
        });
        
        // Atualizar o total automaticamente
        updateChartTotal('retirementChart', retirementTotal);
    }

    // Gráfico 2 - Vencimento e Vantagens Fixas - Pessoa civil
    const salaryCtx = document.getElementById('salaryChart');
    if (salaryCtx) {
        // Dados do gráfico
        const salaryData = [
            { filled: 87, empty: 30 }, // Anel externo
            { filled: 87, empty: 30 },   // Anel médio
            { filled: 86, empty: 30 }    // Anel interno
        ];
        
        // Calcular total (soma dos valores preenchidos)
        const salaryTotal = salaryData.reduce((sum, ring) => sum + ring.filled, 0);
        
        new Chart(salaryCtx, {
            type: 'doughnut',
            data: {
                datasets: [
                    {
                        data: [salaryData[0].filled, salaryData[0].empty],
                        backgroundColor: ['#AA79FE', '#FFF2FE'],
                        borderWidth: 1,
                        borderColor: '#F7F7F7',
                        cutout: '60%'
                    },
                    {
                        data: [salaryData[1].filled, salaryData[1].empty],
                        backgroundColor: ['#7A34F3', '#FFF2FE'],
                        borderWidth: 1,
                        borderColor: '#F7F7F7',
                        cutout: '60%'
                    },
                    {
                        data: [salaryData[2].filled, salaryData[2].empty],
                        backgroundColor: ['#422278', '#FFF2FE'],
                        borderWidth: 1,
                        borderColor: '#F7F7F7',
                        cutout: '60%'
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: getTooltipConfig('Vencimentos e Vantagens')
                }
            }
        });
        
        // Atualizar o total automaticamente
        updateChartTotal('salaryChart', salaryTotal);
    }

    // Gráfico 3 - A detalhar
    const detailCtx = document.getElementById('detailChart');
    if (detailCtx) {
        // Dados do gráfico
        const detailData = [
            { filled: 21, empty: 10 }, // Anel externo
            { filled: 21, empty: 10 },   // Anel médio
            { filled: 21, empty: 10 }    // Anel interno
        ];
        
        // Calcular total (soma dos valores preenchidos)
        const detailTotal = detailData.reduce((sum, ring) => sum + ring.filled, 0);
        
        new Chart(detailCtx, {
            type: 'doughnut',
            data: {
                datasets: [
                    {
                        data: [detailData[0].filled, detailData[0].empty],
                        backgroundColor: ['#AB2D2D', '#F7F7F7'],
                        borderWidth: 1,
                        borderColor: '#F7F7F7',
                        cutout: '60%'
                    },
                    {
                        data: [detailData[1].filled, detailData[1].empty],
                        backgroundColor: ['#F19F42', '#F7F7F7'],
                        borderWidth: 1,
                        borderColor: '#F7F7F7',
                        cutout: '60%'
                    },
                    {
                        data: [detailData[2].filled, detailData[2].empty],
                        backgroundColor: ['#E7D551', '#F7F7F7'],
                        borderWidth: 1,
                        borderColor: '#F7F7F7',
                        cutout: '60%'
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: getTooltipConfig('A Detalhar')
                }
            }
        });
        
        // Atualizar o total automaticamente
        updateChartTotal('detailChart', detailTotal);
    }

    // Gráfico 4 - Aposentadorias, Reserva Remunerada e Reformas
    const retirementChart2Ctx = document.getElementById('retirementChart2');
    if (retirementChart2Ctx) {
        const retirementChart2Data = [
            { filled: 101, empty: 56 }, // Anel externo
            { filled: 101, empty: 56 },   // Anel médio
        ];
        const retirementChart2Total = retirementChart2Data.reduce((sum, ring) => sum + ring.filled, 0);
        
        new Chart(retirementChart2Ctx, {
            type: 'doughnut',
            data: {
                datasets: [
                    {
                        data: [retirementChart2Data[0].filled, retirementChart2Data[0].empty],
                        backgroundColor: ['#AFD1AA', '#B2D1DA'],
                        borderWidth: 1,
                        borderColor: '#F7F7F7',
                        cutout: '50%'
                    },
                    {
                        data: [retirementChart2Data[1].filled, retirementChart2Data[1].empty],
                        backgroundColor: ['#31652B', '#B2D1DA'],
                        borderWidth: 1,
                        borderColor: '#F7F7F7',
                        cutout: '60%'
                    },
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { 
                    legend: { display: false },
                    tooltip: getTooltipConfig('Aposentadorias e Reformas')
                }
            }
        });
        updateChartTotal('retirementChart2', retirementChart2Total);
    }

    // Gráfico 5 - Vencimento e Vantagens Fixas - Pessoa civil
    const salaryChart2Ctx = document.getElementById('salaryChart2');
    if (salaryChart2Ctx) {
        const salaryChart2Data = [
            { filled: 101, empty: 56 }, // Anel externo
            { filled: 101, empty: 56 },   // Anel médio
        ];
        const salaryChart2Total = salaryChart2Data.reduce((sum, ring) => sum + ring.filled, 0);
        
        new Chart(salaryChart2Ctx, {
            type: 'doughnut',
            data: {
                datasets: [
                    {
                        data: [salaryChart2Data[0].filled, salaryChart2Data[0].empty],
                        backgroundColor: ['#AFD1AA', '#B2D1DA'],
                        borderWidth: 1,
                        borderColor: '#F7F7F7',
                        cutout: '50%'
                    },
                    {
                        data: [salaryChart2Data[1].filled, salaryChart2Data[1].empty],
                        backgroundColor: ['#31652B', '#B2D1DA'],
                        borderWidth: 1,
                        borderColor: '#F7F7F7',
                        cutout: '60%'
                    },
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { 
                    legend: { display: false },
                    tooltip: getTooltipConfig('Vencimentos e Vantagens')
                }
            }
        });
        updateChartTotal('salaryChart2', salaryChart2Total);
    }

    // Gráfico 6 - Concessão de Bolsas para Pesquisa
    const scholarshipCtx = document.getElementById('scholarshipChart');
    if (scholarshipCtx) {
        const scholarshipData = [
            { filled: 101, empty: 56 }, // Anel externo
            { filled: 101, empty: 56 },   // Anel médio
        ];
        const scholarshipTotal = scholarshipData.reduce((sum, ring) => sum + ring.filled, 0);
        
        new Chart(scholarshipCtx, {
            type: 'doughnut',
            data: {
                datasets: [
                    {
                        data: [scholarshipData[0].filled, scholarshipData[0].empty],
                        backgroundColor: ['#AFD1AA', '#B2D1DA'],
                        borderWidth: 1,
                        borderColor: '#F7F7F7',
                        cutout: '50%'
                    },
                    {
                        data: [scholarshipData[1].filled, scholarshipData[1].empty],
                        backgroundColor: ['#31652B', '#B2D1DA'],
                        borderWidth: 1,
                        borderColor: '#F7F7F7',
                        cutout: '60%'
                    },
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { 
                    legend: { display: false },
                    tooltip: getTooltipConfig('Concessão de Bolsas')
                }
            }
        });
        updateChartTotal('scholarshipChart', scholarshipTotal);
    }

    // Gráfico 7 - Aposentadorias, Reserva Remunerada e Reformas
    const retirementChart3Ctx = document.getElementById('retirementChart3');
    if (retirementChart3Ctx) {
        const retirementChart3Data = [
            { filled: 101, empty: 56 }, // Anel externo
            { filled: 101, empty: 56 },   // Anel médio
        ];
        const retirementChart3Total = retirementChart3Data.reduce((sum, ring) => sum + ring.filled, 0);
        
        new Chart(retirementChart3Ctx, {
            type: 'doughnut',
            data: {
                datasets: [
                    {
                        data: [retirementChart3Data[0].filled, retirementChart3Data[0].empty],
                        backgroundColor: ['#AFD1AA', '#B2D1DA'],
                        borderWidth: 1,
                        borderColor: '#F7F7F7',
                        cutout: '50%'
                    },
                    {
                        data: [retirementChart3Data[1].filled, retirementChart3Data[1].empty],
                        backgroundColor: ['#31652B', '#B2D1DA'],
                        borderWidth: 1,
                        borderColor: '#F7F7F7',
                        cutout: '60%'
                    },
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { 
                    legend: { display: false },
                    tooltip: getTooltipConfig('Aposentadorias e Reformas')
                }
            }
        });
        updateChartTotal('retirementChart3', retirementChart3Total);
    }

    // Gráfico 8 - Aposentadorias, Reserva Remunerada e Reformas
    const retirementChart4Ctx = document.getElementById('retirementChart4');
    if (retirementChart4Ctx) {
        const retirementChart4Data = [
            { filled: 101, empty: 56 }, // Anel externo
            { filled: 101, empty: 56 },   // Anel médio
        ];
        const retirementChart4Total = retirementChart4Data.reduce((sum, ring) => sum + ring.filled, 0);
        
        new Chart(retirementChart4Ctx, {
            type: 'doughnut',
            data: {
                datasets: [
                    {
                        data: [retirementChart4Data[0].filled, retirementChart4Data[0].empty],
                        backgroundColor: ['#AFD1AA', '#B2D1DA'],
                        borderWidth: 1,
                        borderColor: '#F7F7F7',
                        cutout: '50%'
                    },
                    {
                        data: [retirementChart4Data[1].filled, retirementChart4Data[1].empty],
                        backgroundColor: ['#31652B', '#B2D1DA'],
                        borderWidth: 1,
                        borderColor: '#F7F7F7',
                        cutout: '60%'
                    },
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { 
                    legend: { display: false },
                    tooltip: getTooltipConfig('Aposentadorias e Reformas')
                }
            }
        });
        updateChartTotal('retirementChart4', retirementChart4Total);
    }

    // Gráfico 9 - Vencimento e Vantagens Fixas - Pessoa civil
    const salaryChart3Ctx = document.getElementById('salaryChart3');
    if (salaryChart3Ctx) {
        const salaryChart3Data = [
            { filled: 101, empty: 56 }, // Anel externo
            { filled: 101, empty: 56 },   // Anel médio
        ];
        const salaryChart3Total = salaryChart3Data.reduce((sum, ring) => sum + ring.filled, 0);
        
        new Chart(salaryChart3Ctx, {
            type: 'doughnut',
            data: {
                datasets: [
                    {
                        data: [salaryChart3Data[0].filled, salaryChart3Data[0].empty],
                        backgroundColor: ['#AFD1AA', '#B2D1DA'],
                        borderWidth: 1,
                        borderColor: '#F7F7F7',
                        cutout: '50%'
                    },
                    {
                        data: [salaryChart3Data[1].filled, salaryChart3Data[1].empty],
                        backgroundColor: ['#31652B', '#B2D1DA'],
                        borderWidth: 1,
                        borderColor: '#F7F7F7',
                        cutout: '60%'
                    },
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { 
                    legend: { display: false },
                    tooltip: getTooltipConfig('Vencimentos e Vantagens')
                }
            }
        });
        updateChartTotal('salaryChart3', salaryChart3Total);
    }

    // Gráfico 10 - Vencimento e Vantagens Fixas - Pessoa civil
    const salaryChart4Ctx = document.getElementById('salaryChart4');
    if (salaryChart4Ctx) {
        const salaryChart4Data = [
            { filled: 101, empty: 56 }, // Anel externo
            { filled: 101, empty: 56 },   // Anel médio
        ];
        const salaryChart4Total = salaryChart4Data.reduce((sum, ring) => sum + ring.filled, 0);
        
        new Chart(salaryChart4Ctx, {
            type: 'doughnut',
            data: {
                datasets: [
                    {
                        data: [salaryChart4Data[0].filled, salaryChart4Data[0].empty],
                        backgroundColor: ['#AFD1AA', '#B2D1DA'],
                        borderWidth: 1,
                        borderColor: '#F7F7F7',
                        cutout: '50%'
                    },
                    {
                        data: [salaryChart4Data[1].filled, salaryChart4Data[1].empty],
                        backgroundColor: ['#31652B', '#B2D1DA'],
                        borderWidth: 1,
                        borderColor: '#F7F7F7',
                        cutout: '60%'
                    },
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { 
                    legend: { display: false },
                    tooltip: getTooltipConfig('Vencimentos e Vantagens')
                }
            }
        });
        updateChartTotal('salaryChart4', salaryChart4Total);
    }

    // Gráfico 11 - [A detalhar]
    const detailChart2Ctx = document.getElementById('detailChart2');
    if (detailChart2Ctx) {
        const detailChart2Data = [
            { filled: 101, empty: 56 }, // Anel externo
            { filled: 101, empty: 56 },   // Anel médio
        ];
        const detailChart2Total = detailChart2Data.reduce((sum, ring) => sum + ring.filled, 0);
        
        new Chart(detailChart2Ctx, {
            type: 'doughnut',
            data: {
                datasets: [
                    {
                        data: [detailChart2Data[0].filled, detailChart2Data[0].empty],
                        backgroundColor: ['#AFD1AA', '#B2D1DA'],
                        borderWidth: 1,
                        borderColor: '#F7F7F7',
                        cutout: '50%'
                    },
                    {
                        data: [detailChart2Data[1].filled, detailChart2Data[1].empty],
                        backgroundColor: ['#31652B', '#B2D1DA'],
                        borderWidth: 1,
                        borderColor: '#F7F7F7',
                        cutout: '60%'
                    },
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { 
                    legend: { display: false },
                    tooltip: getTooltipConfig('A Detalhar')
                }
            }
        });
        updateChartTotal('detailChart2', detailChart2Total);
    }

    // Gráfico 12 - [A detalhar]
    const detailChart3Ctx = document.getElementById('detailChart3');
    if (detailChart3Ctx) {
        const detailChart3Data = [
            { filled: 101, empty: 56 }, // Anel externo
            { filled: 101, empty: 56 },   // Anel médio
        ];
        const detailChart3Total = detailChart3Data.reduce((sum, ring) => sum + ring.filled, 0);
        
        new Chart(detailChart3Ctx, {
            type: 'doughnut',
            data: {
                datasets: [
                    {
                        data: [detailChart3Data[0].filled, detailChart3Data[0].empty],
                        backgroundColor: ['#AFD1AA', '#B2D1DA'],
                        borderWidth: 1,
                        borderColor: '#F7F7F7',
                        cutout: '50%'
                    },
                    {
                        data: [detailChart3Data[1].filled, detailChart3Data[1].empty],
                        backgroundColor: ['#31652B', '#B2D1DA'],
                        borderWidth: 1,
                        borderColor: '#F7F7F7',
                        cutout: '60%'
                    },
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { 
                    legend: { display: false },
                    tooltip: getTooltipConfig('A Detalhar')
                }
            }
        });
        updateChartTotal('detailChart3', detailChart3Total);
    }
}

// Função para criar o gráfico de contratos
function createContractsChart() {
    const ctx = document.getElementById('contractsChart');
    if (!ctx) return;

    const chartData = {
        labels: [
            'Serviços',
            'Compras',
            'Informática',
            'Mão de obra',
            'Serviços de Engenharia',
            'Cessão'
        ],
        datasets: [{
            data: [59.54, 24.81, 8.78, 3.82, 2.67, 0.38],
            backgroundColor: [
                '#AB2D2D',
                '#FB8585',
                '#31652B',
                '#67A95E',
                '#326879',
                '#8B4513'
            ],
            borderWidth: 0,
            cutout: '60%'
        }]
    };

    const config = {
        type: 'doughnut',
        data: chartData,
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    backgroundColor: '#422278',
                    titleColor: '#FFFFFF',
                    bodyColor: '#FFFFFF',
                    padding: 16,
                    cornerRadius: 8,
                    displayColors: true,
                    borderColor: '#7A34F3',
                    borderWidth: 1,
                    titleFont: {
                        size: 14,
                        weight: '600',
                        family: 'Inter'
                    },
                    bodyFont: {
                        size: 13,
                        weight: '400',
                        family: 'Inter'
                    },
                    callbacks: {
                        title: function(context) {
                            return 'Contratos por Categoria';
                        },
                        label: function(context) {
                            return context.label + ': ' + context.parsed.toLocaleString('pt-BR') + '%';
                        }
                    }
                }
            },
            elements: { arc: { borderWidth: 0 } }
        }
    };

    new Chart(ctx, config);
}

// Carregar e desenhar os gráficos "Como o dinheiro está sendo gasto?" a partir do JSON
function loadExpenseElementCharts() {
    const dataUrl = '../public/data/orcamento_por_elemento_despesa.json';
    const urlWithBust = `${dataUrl}?v=${Date.now()}`;

    function safeNum(v) { return Number(v) || 0; }

    // Mantém o esquema de cores original por gráfico
    function getRingColors(canvasId) {
        // [empenhado, pagas, aPagar]
        const purple = ['#AA79FE', '#7A34F3', '#422278'];
        const green = ['#AFD1AA', '#31652B', '#B2D1DA'];
        const warm  = ['#AB2D2D', '#F19F42', '#E7D551'];
        switch (canvasId) {
            case 'retirementChart':
            case 'salaryChart':
                return purple;
            case 'detailChart':
                return warm;
            // Segunda, terceira e quarta linhas originais usavam verdes
            case 'retirementChart2':
            case 'salaryChart2':
            case 'scholarshipChart':
            case 'retirementChart3':
            case 'retirementChart4':
            case 'salaryChart3':
            case 'salaryChart4':
            case 'detailChart2':
            case 'detailChart3':
                return green;
            default:
                return green;
        }
    }

    function createElementDonut(canvasId, record) {
        const ctx = document.getElementById(canvasId);
        if (!ctx || !record) return;

        // Base prioriza dotação; se ausente, usa empenhado; senão soma de pagas + a pagar
        const dotacao = safeNum(record.dotacao);
        const empenhado = safeNum(record.orcamento_alocado_empenhado);
        const pagas = safeNum(record.despesas_pagas);
        const aPagar = safeNum(record.despesas_programas_a_pagar);
        const base = dotacao > 0 ? dotacao : (empenhado > 0 ? empenhado : (pagas + aPagar));
        if (base <= 0) return;

        const valEmpenhado = Math.max(Math.min(empenhado, base), 0);
        const valPagas = Math.max(Math.min(pagas, base), 0);
        const valAPagar = Math.max(Math.min(aPagar, base), 0);

        // destrói gráfico anterior se existir
        window.__govhubCharts = window.__govhubCharts || {};
        if (window.__govhubCharts[canvasId]) {
            try { window.__govhubCharts[canvasId].destroy(); } catch (e) {}
        }

        const [cEmp, cPag, cAPag] = getRingColors(canvasId);

        const chartInstance = new Chart(ctx, {
            type: 'doughnut',
            data: {
                datasets: [
                    { label: 'orcamento_alocado_empenhado', data: [valEmpenhado, Math.max(base - valEmpenhado, 0)], backgroundColor: [cEmp, 'rgba(0,0,0,0)'], borderWidth: 1, borderColor: '#F7F7F7', cutout: '60%' },
                    { label: 'despesas_pagas', data: [valPagas, Math.max(base - valPagas, 0)], backgroundColor: [cPag, 'rgba(0,0,0,0)'], borderWidth: 1, borderColor: '#F7F7F7', cutout: '60%' },
                    { label: 'despesas_programas_a_pagar', data: [valAPagar, Math.max(base - valAPagar, 0)], backgroundColor: [cAPag, 'rgba(0,0,0,0)'], borderWidth: 1, borderColor: '#F7F7F7', cutout: '60%' }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        backgroundColor: '#422278',
                        titleColor: '#FFFFFF',
                        bodyColor: '#FFFFFF',
                        padding: 12,
                        borderColor: '#7A34F3',
                        borderWidth: 1,
                        displayColors: true,
                        filter: function(item) { return item.dataIndex === 0; },
                        callbacks: {
                            title: function(items) {
                                // mostra a chave do campo do JSON como título
                                if (!items || !items.length) return '';
                                const dsLabel = items[0].dataset.label || '';
                                const map = {
                                    'orcamento_alocado_empenhado': 'Orçamento alocado (empenhado)',
                                    'despesas_pagas': 'Despesas pagas',
                                    'despesas_programas_a_pagar': 'Despesas programadas (a pagar)'
                                };
                                return map[dsLabel] || dsLabel;
                            },
                            label: function(context) {
                                const raw = context.parsed;
                                const formatted = (typeof raw === 'number') ? raw.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : raw;
                                return formatted;
                            }
                        }
                    }
                }
            }
        });

        window.__govhubCharts[canvasId] = chartInstance;

        // Atualiza o valor central como Dotação (ou base) em milhões
        const totalMillions = Math.round((dotacao > 0 ? dotacao : base) / 1_000_000);
        updateChartTotal(canvasId, totalMillions);

        // Atualiza o título do card para o nome do elemento de despesa do JSON
        const card = ctx.closest('.dashboard-card');
        if (card) {
            const titleEl = card.querySelector('.dashboard-title');
            if (titleEl && record.elemento_despesa_desc) {
                titleEl.textContent = record.elemento_despesa_desc;
            }
        }
    }

    function indexByDesc(rows) {
        const map = new Map();
        rows.forEach(r => map.set((r.elemento_despesa_desc || '').toUpperCase(), r));
        return map;
    }

    fetch(urlWithBust, { cache: 'no-store' })
        .then(r => { if (!r.ok) throw new Error('fetch not ok'); return r.json(); })
        .then(json => {
            let rows = Array.isArray(json) ? json.slice() : [];
            // Empurra "[A DETALHAR]" para o final
            rows.sort((a,b) => {
                const ad = (a.elemento_despesa_desc || '').toUpperCase() === '[A DETALHAR]';
                const bd = (b.elemento_despesa_desc || '').toUpperCase() === '[A DETALHAR]';
                if (ad && !bd) return 1;
                if (!ad && bd) return -1;
                return 0;
            });
            const byDesc = indexByDesc(rows);

            const mapping = [
                { id: 'retirementChart', key: 'APOSENTADORIAS, RESERVA REMUNERADA E REFORMAS' },
                { id: 'salaryChart', key: 'VENCIMENTOS E VANTAGENS FIXAS - PESSOAL CIVIL' },
                { id: 'detailChart', key: '[A DETALHAR]' },
                { id: 'retirementChart2', key: 'LOCACAO DE MAO-DE-OBRA' },
                { id: 'salaryChart2', key: 'OBRIGACOES PATRONAIS' },
                { id: 'scholarshipChart', key: 'AUXILIO FINANCEIRO A PESQUISADORES' },
                { id: 'retirementChart3', key: 'PENSOES' },
                { id: 'retirementChart4', key: 'INDENIZACOES E RESTITUICOES' },
                { id: 'salaryChart3', key: 'SERVICOS DE TECNOLOGIA DA INFORMACAO E COMUNICACAO - PJ' },
                { id: 'salaryChart4', key: 'CONTRIBUICAO A ENTIDADE FECHADA PREVIDENCIA' },
                { id: 'detailChart2', key: 'OUTROS SERVICOS DE TERCEIROS PJ - OP.INT.ORC.' },
                { id: 'detailChart3', key: 'DIARIAS - PESSOAL CIVIL' }
            ];

            const usedKeys = new Set();
            mapping.forEach(({ id, key }) => {
                const rec = byDesc.get(key);
                if (rec) {
                    usedKeys.add(key);
                    createElementDonut(id, rec);
                }
            });

            // Renderizar cartões adicionais para elementos não mapeados
            const remaining = rows.filter(r => !usedKeys.has((r.elemento_despesa_desc || '').toUpperCase()));
            if (remaining.length > 0) {
                const container = document.querySelector('.expenses-section .container');
                if (container) {
                    let rowDiv = null;
                    remaining.forEach((rec, idx) => {
                        if (idx % 3 === 0) {
                            rowDiv = document.createElement('div');
                            rowDiv.className = 'row g-4 mb-4';
                            container.appendChild(rowDiv);
                        }
                        const col = document.createElement('div');
                        col.className = 'col-12 col-lg-4';
                        const card = document.createElement('div');
                        card.className = 'dashboard-card';
                        const title = document.createElement('h6');
                        title.className = 'dashboard-title';
                        title.textContent = rec.elemento_despesa_desc || '';
                        const chartContainer = document.createElement('div');
                        chartContainer.className = 'dashboard-chart-container';
                        const canvas = document.createElement('canvas');
                        const canvasId = `dynamicChart_${idx}`;
                        canvas.id = canvasId;
                        canvas.width = 200;
                        canvas.height = 200;
                        const center = document.createElement('div');
                        center.className = 'chart-center-text';
                        const num = document.createElement('span');
                        num.className = 'chart-total-number';
                        num.textContent = '0M';
                        const label = document.createElement('span');
                        label.className = 'chart-total-label';
                        label.textContent = 'Dotação';
                        center.appendChild(num);
                        center.appendChild(label);
                        chartContainer.appendChild(canvas);
                        chartContainer.appendChild(center);
                        card.appendChild(title);
                        card.appendChild(chartContainer);
                        col.appendChild(card);
                        rowDiv.appendChild(col);
                        createElementDonut(canvasId, rec);
                    });
                }
            }

            // Mover todos os cards "[A DETALHAR]" para o final visualmente
            const container = document.querySelector('.expenses-section .container');
            if (container) {
                const detailCols = Array.from(container.querySelectorAll('.dashboard-card .dashboard-title'))
                    .filter(h => (h.textContent || '').trim().toUpperCase() === '[A DETALHAR]')
                    .map(h => h.closest('.col-12.col-lg-4'));
                if (detailCols.length) {
                    // cria uma nova linha ao final para agrupar os "A DETALHAR"
                    const detailRow = document.createElement('div');
                    detailRow.className = 'row g-4 mb-4';
                    container.appendChild(detailRow);
                    detailCols.forEach(col => {
                        if (col && col.parentElement) {
                            detailRow.appendChild(col);
                        }
                    });
                }
                // Reflow: reconstroi as linhas em grupos de 3 para eliminar buracos visuais
                const allCols = Array.from(container.querySelectorAll('.col-12.col-lg-4'));
                // Remove todas as linhas atuais
                Array.from(container.querySelectorAll('.row.g-4.mb-4')).forEach(row => row.remove());
                // Recria as linhas com 3 colunas por linha
                for (let i = 0; i < allCols.length; i += 3) {
                    const row = document.createElement('div');
                    row.className = 'row g-4 mb-4';
                    container.appendChild(row);
                    allCols.slice(i, i + 3).forEach(col => row.appendChild(col));
                }
            }
        })
        .catch(() => {
            // mantém gráficos estáticos se falhar
        });
}

// Função para inicializar funcionalidades específicas da página de dashboards
function initDashboards() {
    // Criar o gráfico quando o DOM estiver carregado
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => {
            createBudgetChart();
            createContractsChart();
            createDashboardCharts();
        });
    } else {
        createBudgetChart();
        createContractsChart();
        createDashboardCharts();
    }
    
    console.log('📊 Página Dashboards inicializada com sucesso!');
}

// ========================================
// ECHARTS CHARTS - GENDER AND RACE DISTRIBUTION
// ========================================

// Função para criar o gráfico em formato V para distribuição por gênero
function createGenderVChart() {
    const container = document.getElementById('genderChart');
    container.innerHTML = '';
}

// Função para criar o treemap de distribuição por raça/cor
function createRaceTreemap() {
    const chartDom = document.getElementById('raceChart');
    if (!chartDom) return;
    
    const myChart = echarts.init(chartDom);
    
    const data = [
        {
            name: 'Brancos',
            value: 700,
            itemStyle: { 
                color: '#FF8C00',
                borderColor: '#ffffff',
                borderWidth: 2
            }
        },
        {
            name: 'Pardos',
            value: 230,
            itemStyle: { 
                color: '#FFA500',
                borderColor: '#ffffff',
                borderWidth: 2
            }
        },
        {
            name: 'Pretos',
            value: 54,
            itemStyle: { 
                color: '#8A2BE2',
                borderColor: '#ffffff',
                borderWidth: 2
            }
        },
        {
            name: 'Amarelos',
            value: 27,
            itemStyle: { 
                color: '#9370DB',
                borderColor: '#ffffff',
                borderWidth: 2
            }
        },
        {
            name: 'Não informados',
            value: 18,
            itemStyle: { 
                color: '#DDA0DD',
                borderColor: '#ffffff',
                borderWidth: 2
            }
        },
        {
            name: 'Indígenas',
            value: 3,
            itemStyle: { 
                color: '#9932CC',
                borderColor: '#ffffff',
                borderWidth: 2
            }
        }
    ];
    
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
                name: 'Distribuição por Raça/Cor',
                type: 'treemap',
                data: data,
                roam: false,
                nodeClick: false,
                breadcrumb: {
                    show: false
                },
                label: {
                    show: true,
                    formatter: function(params) {
                        // Mostrar números e nomes para blocos grandes
                        // Blocos pequenos (Não informados e Indígenas) ficam sem texto
                        if (params.value >= 20) {
                            return params.value + '\n' + params.name;
                        } else {
                            return ''; // Sem texto para blocos pequenos
                        }
                    },
                    fontSize: function(params) {
                        // Tamanho de fonte baseado no valor
                        if (params.value >= 500) return 16;
                        if (params.value >= 100) return 14;
                        if (params.value >= 50) return 12;
                        return 10;
                    },
                    fontWeight: 'bold',
                    color: '#ffffff',
                    fontFamily: 'Inter',
                    textShadowColor: 'rgba(0,0,0,0.5)',
                    textShadowBlur: 2,
                    position: 'inside',
                    align: 'center',
                    verticalAlign: 'middle'
                },
                upperLabel: {
                    show: false
                },
                itemStyle: {
                    borderColor: '#ffffff',
                    borderWidth: 1,
                    borderRadius: 0
                },
                emphasis: {
                    itemStyle: {
                        borderColor: '#7A34F3',
                        borderWidth: 2
                    }
                },
                gapWidth: 0,
                gapHeight: 0,
                levels: [
                    {
                        itemStyle: {
                            borderColor: '#ffffff',
                            borderWidth: 1,
                            gapWidth: 0,
                            gapHeight: 0
                        }
                    }
                ]
            }
        ]
    };
    
    myChart.setOption(option);
    
    // Adicionar legenda para "Não informados" e "Indígenas"
    const legendContainer = document.createElement('div');
    legendContainer.style.cssText = `
        display: flex;
        justify-content: right;
        gap: 20px;
        margin-top: 10px;
        font-family: Inter, sans-serif;
    `;
    
    const naoInformados = document.createElement('div');
    naoInformados.style.cssText = `
        display: flex;
        align-items: right;
        gap: 8px;
        font-size: 14px;
        color: #1f2937;
    `;
    
    const naoInformadosDot = document.createElement('div');
    naoInformadosDot.style.cssText = `
        width: 12px;
        height: 12px;
        background-color: #DDA0DD;
        border-radius: 50%;
    `;
    
    naoInformados.appendChild(naoInformadosDot);
    naoInformados.appendChild(document.createTextNode('18 Não informados'));
    
    const indigenas = document.createElement('div');
    indigenas.style.cssText = `
        display: flex;
        align-items: center;
        gap: 8px;
        font-size: 14px;
        color: #1f2937;
    `;
    
    const indigenasDot = document.createElement('div');
    indigenasDot.style.cssText = `
        width: 12px;
        height: 12px;
        background-color: #9932CC;
        border-radius: 50%;
    `;
    
    indigenas.appendChild(indigenasDot);
    indigenas.appendChild(document.createTextNode('4 Indígenas'));
    
    legendContainer.appendChild(naoInformados);
    legendContainer.appendChild(indigenas);
    
    // Adicionar a legenda ao container do gráfico
    const chartContainer = document.getElementById('raceChart').parentElement;
    chartContainer.appendChild(legendContainer);
    
    // Responsive
    window.addEventListener('resize', function() {
        myChart.resize();
    });
}

// Função para inicializar funcionalidades específicas da página de dashboards
function initDashboards() {
    // Criar o gráfico quando o DOM estiver carregado
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => {
            createBudgetChart();
            createContractsChart();
            // createDashboardCharts(); // removido para evitar gráficos duplicados
            loadExpenseElementCharts();
            loadBudgetKpis();
            createGenderVChart();
            createRaceTreemap();
        });
    } else {
        createBudgetChart();
        createContractsChart();
        // createDashboardCharts(); // removido para evitar gráficos duplicados
        loadExpenseElementCharts();
        loadBudgetKpis();
        createGenderVChart();
        createRaceTreemap();
    }
    
    console.log('📊 Página Dashboards inicializada com sucesso!');
}

// Inicializar quando o script for carregado
initDashboards();

// Exportar funções para uso global
window.createBudgetChart = createBudgetChart;
window.createContractsChart = createContractsChart;
window.createDashboardCharts = createDashboardCharts;
window.createGenderVChart = createGenderVChart;
window.createRaceTreemap = createRaceTreemap;
window.initDashboards = initDashboards;

