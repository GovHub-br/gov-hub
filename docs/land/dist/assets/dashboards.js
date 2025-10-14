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
    console.log('🚀 Inicializando dashboards...');
    
    // Criar o gráfico quando o DOM estiver carregado
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => {
            console.log('📄 DOM carregado, criando gráficos...');
            createBudgetChart();
            createAposentadoriasChart();
        });
    } else {
        console.log('📄 DOM já carregado, criando gráficos...');
        createBudgetChart();
        createAposentadoriasChart();
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

// Carregar KPIs de contratos a partir do JSON público
function loadContractsKpis() {
    const dataUrl = '../public/data/orcamento_contratos.json';
    const urlWithBust = `${dataUrl}?v=${Date.now()}`;

    function formatCurrency(value) {
        return (Number(value) || 0).toLocaleString('pt-BR', {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
        });
    }

    function setValue(id, value) {
        const el = document.getElementById(id);
        if (el) {
            el.textContent = formatCurrency(value);
        }
    }

    fetch(urlWithBust, { cache: 'no-store' })
        .then(resp => {
            if (!resp.ok) throw new Error('fetch not ok');
            return resp.json();
        })
        .then(json => {
            setValue('contratos-alocado-empenhado', json.orcamento_alocado_empenhado);
            setValue('contratos-saldo-empenho', json.saldo_de_empenho_a_liquidar);
            setValue('contratos-despesas-pagas', json.despesas_pagas);
        })
        .catch(() => {
            // mantém valores existentes se falhar
        });
}

// Carregar gráfico de barras dos maiores contratos
function loadContractsBars() {
    const dataUrl = '../public/data/10_maiores_contratos_natureza_despesa.json';
    const urlWithBust = `${dataUrl}?v=${Date.now()}`;

    function formatValue(value) {
        const num = Number(value) || 0;
        if (num >= 1000000) {
            const millions = num / 1000000;
            // Mostrar 2 casas decimais para valores em milhões para maior precisão
            return millions.toFixed(2).replace('.', ',') + 'M';
        } else if (num >= 1000) {
            const thousands = num / 1000;
            // Mostrar 1 casa decimal para valores em milhares
            return thousands.toFixed(1).replace('.', ',') + 'k';
        }
        return num.toLocaleString('pt-BR', {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
        });
    }

    function getNaturezaDespesa(item) {
        // Determina qual natureza de despesa tem valor
        if (item.locacao_de_mao_de_obra) return 'Locação de mão de obra';
        if (item.outros_servicos_de_terceiros_pj) return 'Outros serviços de terceiros - Pessoa Jurídica';
        if (item.passagens_e_despesas_com_locomocao) return 'Passagens e despesas com locomoção';
        if (item.servicos_de_ti_pj) return 'Serviços de TI - Pessoa Jurídica';
        return 'Não especificado';
    }

    function getValorTotal(item) {
        return (item.locacao_de_mao_de_obra || 0) + 
               (item.outros_servicos_de_terceiros_pj || 0) + 
               (item.passagens_e_despesas_com_locomocao || 0) + 
               (item.servicos_de_ti_pj || 0);
    }

    function getCorNatureza(natureza) {
        const cores = {
            'Locação de mão de obra': '#7A34F3',
            'Outros serviços de terceiros - Pessoa Jurídica': '#31652B',
            'Passagens e despesas com locomoção': '#F59E0B',
            'Serviços de TI - Pessoa Jurídica': '#AB2D2D',
            'Não especificado': '#326879'
        };
        return cores[natureza] || '#326879';
    }

    fetch(urlWithBust, { cache: 'no-store' })
        .then(resp => {
            if (!resp.ok) throw new Error('fetch not ok');
            return resp.json();
        })
        .then(json => {
            const container = document.getElementById('contracts-bars-container');
            if (!container) return;

            // Ordenar por valor total (maior para menor)
            const sortedData = json
                .map(item => ({
                    ...item,
                    valorTotal: getValorTotal(item),
                    natureza: getNaturezaDespesa(item)
                }))
                .sort((a, b) => b.valorTotal - a.valorTotal);

            // Encontrar o valor máximo para calcular percentuais
            const maxValue = Math.max(...sortedData.map(item => item.valorTotal));

            // Limpar container
            container.innerHTML = '';

            // Criar barras dinamicamente
            sortedData.forEach((item, index) => {
                const percentage = (item.valorTotal / maxValue) * 100;
                const formattedValue = formatValue(item.valorTotal);
                const cor = getCorNatureza(item.natureza);

                const barItem = document.createElement('div');
                barItem.className = 'contracts-bar-item';
                barItem.innerHTML = `
                    <div class="contracts-bar-header">
                        <span class="contracts-bar-value">${formattedValue}</span>
                        <span class="contracts-bar-label">${item.fornecedor_nome}</span>
                    </div>
                    <div class="contracts-bar-track">
                        <div class="contracts-bar-fill" style="width: ${percentage.toFixed(1)}%; background-color: ${cor};"></div>
                    </div>
                `;

                container.appendChild(barItem);
            });
        })
        .catch(() => {
            // mantém valores existentes se falhar
        });
}

// Carregar KPIs de TEDs recebidos
function loadTedsRecebidosKpis() {
    const dataUrl = '../public/data/teds_recebidos.json';
    const urlWithBust = `${dataUrl}?v=${Date.now()}`;

    function formatCurrency(value) {
        return (Number(value) || 0).toLocaleString('pt-BR', {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
        });
    }

    function setValue(id, value) {
        const el = document.getElementById(id);
        if (el) {
            el.textContent = value;
        }
    }

    fetch(urlWithBust, { cache: 'no-store' })
        .then(resp => {
            if (!resp.ok) throw new Error('fetch not ok');
            return resp.json();
        })
        .then(json => {
            setValue('teds-recebidos-total', json.teds_recebidos);
            setValue('teds-proximos-finalizar', json.teds_proximos_finalizar);
            setValue('teds-despesas-liquidar', formatCurrency(json.despesas_a_liquidar_teds));
        })
        .catch(() => {
            // mantém valores existentes se falhar
        });
}

// Carregar KPIs de TEDs enviados
function loadTedsEnviadosKpis() {
    const dataUrl = '../public/data/teds_enviados.json';
    const urlWithBust = `${dataUrl}?v=${Date.now()}`;

    function formatCurrency(value) {
        return (Number(value) || 0).toLocaleString('pt-BR', {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
        });
    }

    function setValue(id, value) {
        const el = document.getElementById(id);
        if (el) {
            el.textContent = formatCurrency(value);
        }
    }

    fetch(urlWithBust, { cache: 'no-store' })
        .then(resp => {
            if (!resp.ok) throw new Error('fetch not ok');
            return resp.json();
        })
        .then(json => {
            setValue('teds-enviados-valor-firmado', json.valor_firmado);
            setValue('teds-enviados-destaque-orcamentario', json.destaque_orcamentario_enviado);
        })
        .catch((err) => {
            console.error('Erro ao carregar KPIs de TEDs enviados:', err);
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

// Função para atualizar a legenda do gráfico de contratos
function updateContractsLegend(labels, counts, percentages) {
    const chartCard = document.getElementById('contractsChart').closest('.chart-card');
    if (!chartCard) return;
    const legend = chartCard.querySelector('.chart-legend');
    if (!legend) return;

    const legendItems = Array.from(legend.querySelectorAll('.legend-item'));
    const count = Math.min(legendItems.length, labels.length, counts.length, percentages.length);

    for (let i = 0; i < count; i++) {
        const item = legendItems[i];
        const textEl = item.querySelector('.legend-text');
        if (!textEl) continue;
        
        const countValue = counts[i];
        const percentage = percentages[i];
        const label = labels[i];
        
        // Formatar percentual com 1 casa decimal
        const formattedPercentage = percentage.toFixed(1).replace('.', ',');
        
        textEl.innerHTML = `<span class="legend-number">${formattedPercentage}%</span> ${label}`;
    }
}

// Função para criar o gráfico de contratos
function createContractsChart() {
    const ctx = document.getElementById('contractsChart');
    if (!ctx) return;

    const dataUrl = '../public/data/contratos.json';
    const urlWithBust = `${dataUrl}?v=${Date.now()}`;

    fetch(urlWithBust, { cache: 'no-store' })
        .then(resp => {
            if (!resp.ok) throw new Error('fetch not ok');
            return resp.json();
        })
        .then(json => {
            const labels = json.map(item => item.categoria);
            const counts = json.map(item => Number(item.count) || 0);
            const total = counts.reduce((sum, count) => sum + count, 0);
            
            // Calcular percentuais
            const percentages = counts.map(count => (count / total) * 100);

            const chartData = {
                labels: labels,
                datasets: [{
                    data: percentages,
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
                                    const index = context.dataIndex;
                                    const count = counts[index];
                                    const percentage = context.parsed;
                                    return context.label + ': ' + count.toLocaleString('pt-BR') + ' contratos (' + percentage.toFixed(1).replace('.', ',') + '%)';
                                }
                            }
                        }
                    },
                    elements: { arc: { borderWidth: 0 } }
                }
            };

            new Chart(ctx, config);
            
            // Atualizar a legenda com os dados reais
            updateContractsLegend(labels, counts, percentages);
        })
        .catch(() => {
            // Fallback com dados estáticos caso o JSON não carregue
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
        });
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
// Função para carregar dados de raça/cor do JSON
async function loadServidoresCorData() {
    try {
        const response = await fetch('../public/data/servidores_cor.json');
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json();
        console.log('✅ Dados de servidores por cor carregados:', data);
        return data;
    } catch (error) {
        console.error('❌ Erro ao carregar dados de servidores por cor:', error);
        return null;
    }
}

// Função para mapear dados do JSON para o formato do gráfico
function mapServidoresCorToChartData(jsonData) {
    if (!jsonData || !Array.isArray(jsonData)) {
        console.error('❌ Dados inválidos para mapeamento');
        return [];
    }

    // Mapeamento de cores para cada raça/cor
    const colorMap = {
        'BRANCA': '#FF8C00',
        'PARDA': '#FFA500', 
        'PRETA': '#8A2BE2',
        'AMARELA': '#9370DB',
        'NAO INFORMADO': '#DDA0DD',
        'INDIGENA': '#9932CC',
        '': '#DDA0DD' // Para valores vazios
    };

    // Filtrar dados válidos e mapear para o formato do gráfico
    const chartData = jsonData
        .filter(item => item.nome_cor && item.cor_ou_raca > 0) // Filtrar apenas dados válidos
        .map(item => ({
            name: item.nome_cor,
            value: item.cor_ou_raca,
            itemStyle: { 
                color: colorMap[item.nome_cor] || '#DDA0DD',
                borderColor: '#ffffff',
                borderWidth: 2
            }
        }))
        .sort((a, b) => b.value - a.value); // Ordenar por valor decrescente

    console.log('📊 Dados mapeados para o gráfico:', chartData);
    return chartData;
}

function createRaceTreemap() {
    const chartDom = document.getElementById('raceChart');
    if (!chartDom) return;
    
    const myChart = echarts.init(chartDom);
    
    // Carregar dados do JSON e criar o gráfico
    loadServidoresCorData().then(jsonData => {
        const data = mapServidoresCorToChartData(jsonData);
        
        if (data.length === 0) {
            console.error('❌ Nenhum dado válido encontrado para o gráfico');
            return;
        }

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
        
        // Buscar valores dinâmicos dos dados
        const naoInformadosData = data.find(item => item.name === 'NAO INFORMADO');
        const indigenasData = data.find(item => item.name === 'INDIGENA');
        
        naoInformados.appendChild(naoInformadosDot);
        naoInformados.appendChild(document.createTextNode(`${naoInformadosData ? naoInformadosData.value : 0} Não informados`));
        
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
        indigenas.appendChild(document.createTextNode(`${indigenasData ? indigenasData.value : 0} Indígenas`));
        
        legendContainer.appendChild(naoInformados);
        legendContainer.appendChild(indigenas);
        
        // Adicionar a legenda ao container do gráfico
        const chartContainer = document.getElementById('raceChart').parentElement;
        chartContainer.appendChild(legendContainer);
        
        // Responsive
        window.addEventListener('resize', function() {
            myChart.resize();
        });
        
    }).catch(error => {
        console.error('❌ Erro ao criar gráfico de raça/cor:', error);
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
            loadContractsKpis();
            loadContractsBars();
            loadTedsRecebidosKpis();
            createGenderVChart();
            createRaceTreemap();
            loadTedsRecebidosTable();
            loadTedsEnviadosTable();
            loadTedsEnviadosKpis();
        });
    } else {
        createBudgetChart();
        createContractsChart();
        // createDashboardCharts(); // removido para evitar gráficos duplicados
        loadExpenseElementCharts();
        loadBudgetKpis();
        loadContractsKpis();
        loadContractsBars();
        loadTedsRecebidosKpis();
        createGenderVChart();
        createRaceTreemap();
        loadTedsRecebidosTable();
        loadTedsEnviadosTable();
        loadTedsEnviadosKpis();
    }
    
    console.log('📊 Página Dashboards inicializada com sucesso!');
}

// Função para carregar e popular a tabela de TEDs recebidos
function loadTedsRecebidosTable() {
    fetch('../public/data/detalhamento_teds_recebidos.json')
        .then(resp => resp.json())
        .then(json => {
            const tbody = document.getElementById('teds-recebidos-tbody');
            if (!tbody) return;
            
            // Limpar tbody
            tbody.innerHTML = '';
            
            // Para cada item do JSON, criar uma linha
            json.forEach(item => {
                const tr = document.createElement('tr');
                
                // Formatar valor monetário
                const valorFormatado = (item.valor_firmado || 0).toLocaleString('pt-BR', {
                    minimumFractionDigits: 2,
                    maximumFractionDigits: 2
                });
                
                // Calcular percentuais
                const percentualTemporal = ((item.percentual_conclusao || 0) * 100).toFixed(2);
                const percentualOrcamentario = item.percentual_conclusao_orcamentaria 
                    ? ((item.percentual_conclusao_orcamentaria || 0) * 100).toFixed(2)
                    : '0';
                
                tr.innerHTML = `
                    <td>
                        <div class="teds-program">
                            <div class="teds-program-code">${item.unidade || ''}</div>
                            <div class="teds-program-text">${item.programa || ''}</div>
                        </div>
                    </td>
                    <td>${item.vigencia || ''}</td>
                    <td>${valorFormatado}</td>
                    <td>
                        <div class="teds-progress">
                            <div class="teds-progress-bar" style="width: ${percentualTemporal}%">
                                <span class="teds-progress-handle" style="left: ${percentualOrcamentario}%"></span>
                            </div>
                        </div>
                    </td>
                `;
                
                tbody.appendChild(tr);
            });
        });
}

// Função para carregar e popular a tabela de TEDs enviados
function loadTedsEnviadosTable() {
    fetch('../public/data/detalhamento_teds_enviados.json')
        .then(resp => resp.json())
        .then(json => {
            const tbody = document.getElementById('teds-enviados-tbody');
            if (!tbody) return;

            // Limpar tbody
            tbody.innerHTML = '';

            // Para cada item do JSON, criar uma linha
            json.forEach(item => {
                const tr = document.createElement('tr');

                // Formatar valor monetário
                const valorFormatado = (item.valor_firmado || 0).toLocaleString('pt-BR', {
                    minimumFractionDigits: 2,
                    maximumFractionDigits: 2
                });

                // Calcular percentuais
                const percentualTemporal = ((item.percentual_conclusao || 0) * 100).toFixed(2);
                const percentualOrcamentario = item.percentual_conclusao_orcamentaria
                    ? ((item.percentual_conclusao_orcamentaria || 0) * 100).toFixed(2)
                    : '0';

                tr.innerHTML = `
                    <td>
                        <div class="teds-sent-program">
                            <div class="teds-sent-program-code">${item.unidade_descentralizadora_responsavel || ''}</div>
                            <div class="teds-sent-program-text">${item.programa || ''}</div>
                        </div>
                    </td>
                    <td>${item.vigencia || ''}</td>
                    <td>${valorFormatado}</td>
                    <td>
                        <div class="teds-sent-progress">
                            <div class="teds-sent-progress-bar" style="width: ${percentualTemporal}%">
                                <span class="teds-progress-handle" style="left: ${percentualOrcamentario}%"></span>
                            </div>
                        </div>
                    </td>
                `;

                tbody.appendChild(tr);
            });
        });
}

// Função para criar o gráfico de linha de aposentadorias
// Baseado em exemplo externo do Chart.js adaptado para dados de aposentadorias
function createAposentadoriasChart() {
    console.log('🔍 Tentando criar gráfico de aposentadorias...');
    const ctx = document.getElementById('aposentadoriasChart');
    if (!ctx) {
        console.error('❌ Canvas aposentadoriasChart não encontrado!');
        return;
    }
    console.log('✅ Canvas encontrado, criando gráfico...');

    // Verificar se Chart.js está carregado
    if (typeof Chart === 'undefined') {
        console.error('❌ Chart.js não está carregado!');
        return;
    }
    console.log('✅ Chart.js carregado, prosseguindo...');

    // Exemplo adaptado de gráfico de linha do Chart.js com dados de aposentadorias
    const data = {
        labels: ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez'],
        datasets: [{
            label: 'Aposentadorias por Mês',
            data: [0, 0, 0, 0, 11, 5, 15, 20, 37, 10, 1, 0],
            borderColor: '#66308F', // Cor roxa baseada em exemplo externo
            backgroundColor: '#66308F',
            borderWidth: 3,
            fill: false,
            tension: 0, // Linha mais angular, menos arredondada
            pointRadius: 0, // Remove os pontos
            pointHoverRadius: 0, // Remove os pontos no hover
            pointBackgroundColor: 'transparent',
            pointBorderColor: 'transparent',
            pointBorderWidth: 0
        }]
    };

    // Configuração baseada em exemplo externo do Chart.js
    const config = {
        type: 'line',
        data: data,
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                intersect: false,
                mode: 'index'
            },
             plugins: {
                 legend: {
                     display: false
                 },
                 tooltip: {
                     enabled: true,
                     backgroundColor: '#66308F',
                     titleColor: '#ffffff',
                     bodyColor: '#ffffff',
                     borderColor: 'transparent',
                     borderWidth: 0,
                     cornerRadius: 8,
                     displayColors: false,
                     padding: 8,
                     titleFont: {
                         family: 'Inter',
                         size: 0
                     },
                     bodyFont: {
                         family: 'Inter',
                         size: 14,
                         weight: 'bold'
                     },
                     callbacks: {
                         title: function() {
                             return '';
                         },
                         label: function(context) {
                             return context.parsed.y.toString();
                         }
                     },
                     // Posicionamento para aparecer abaixo do ponto
                     position: 'nearest',
                     xAlign: 'center',
                     yAlign: 'bottom',
                     caretSize: 8,
                     caretPadding: 4
                 }
             },
            scales: {
                x: {
                    display: true,
                    grid: {
                        color: '#e5e7eb',
                        drawBorder: false,
                        lineWidth: 1
                    },
                    ticks: {
                        color: '#6b7280',
                        font: {
                            family: 'Inter',
                            size: 12,
                            weight: '500'
                        },
                        padding: 8
                    }
                },
                y: {
                    display: true,
                    beginAtZero: true,
                    max: 40,
                    grid: {
                        color: '#e5e7eb',
                        drawBorder: false,
                        lineWidth: 1
                    },
                    ticks: {
                        color: '#6b7280',
                        font: {
                            family: 'Inter',
                            size: 12,
                            weight: '500'
                        },
                        stepSize: 10,
                        padding: 8
                    }
                }
            },
            elements: {
                line: {
                    borderJoinStyle: 'miter', // Junções mais angulares
                    borderCapStyle: 'butt'   // Pontas mais retas
                },
                point: {
                    hoverBackgroundColor: 'transparent',
                    hoverBorderColor: 'transparent',
                    hoverBorderWidth: 0
                }
            }
        }
    };

    new Chart(ctx, config);
    console.log('✅ Gráfico de aposentadorias criado com sucesso!');
}

// Função de fallback para garantir que o gráfico seja criado
function ensureAposentadoriasChart() {
    setTimeout(() => {
        const canvas = document.getElementById('aposentadoriasChart');
        if (canvas && !canvas.chart) {
            console.log('🔄 Tentando criar gráfico novamente...');
            createAposentadoriasChart();
        }
    }, 1000);
}

// Inicializar quando o script for carregado
initDashboards();

// Garantir que o gráfico seja criado
ensureAposentadoriasChart();

// Exportar funções para uso global
window.createBudgetChart = createBudgetChart;
window.createContractsChart = createContractsChart;
window.createDashboardCharts = createDashboardCharts;
window.createGenderVChart = createGenderVChart;
window.createRaceTreemap = createRaceTreemap;
window.createAposentadoriasChart = createAposentadoriasChart;
window.loadTedsRecebidosTable = loadTedsRecebidosTable;
window.loadTedsEnviadosTable = loadTedsEnviadosTable;
window.initDashboards = initDashboards;

