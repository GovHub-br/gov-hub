/* ===================================
   ACOMPANHAMENTO ORÇAMENTÁRIO - GOVHUB
   =================================== */

// Inicialização quando o DOM estiver carregado
document.addEventListener('DOMContentLoaded', function() {
    console.log('Página de Acompanhamento Orçamentário carregada');
    
    // Inicializar gráficos
    initializeCharts();
});

// Função para inicializar os gráficos
function initializeCharts() {
    // Dados mockados baseados no protótipo
    const months = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez'];
    
    // Dados do Tesouro Gerencial
    const tesouroGerencialData = [0, 0, 0, 100, 0, 0, 0, 190, 380, 0, 0, 0];
    
    // Dados do ComprasNet
    const comprasNetPagoData = [0, 0, 0, 0, 0, 350, 0, 0, 0, 0, 0, 0]; // Linha marrom
    const comprasNetCronogramaData = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]; // Linha laranja (plana)
    
    // Configuração comum para os gráficos
    const commonOptions = {
        responsive: true,
        maintainAspectRatio: false,
        layout: {
            padding: {
                top: 5,
                bottom: 5,
                left: 5,
                right: 5
            }
        },
        elements: {
            point: {
                radius: 4,
                hoverRadius: 8,
                hoverBorderWidth: 3,
                borderWidth: 2
            }
        },
        plugins: {
            legend: {
                display: false
            }
        },
        scales: {
            x: {
                grid: {
                    display: false
                },
                ticks: {
                    color: '#6b7280',
                    font: {
                        family: 'Inter',
                        size: 11
                    },
                    padding: 3
                }
            },
            y: {
                beginAtZero: true,
                max: 400,
                grid: {
                    display: true,
                    color: '#f1f5f9',
                    lineWidth: 1
                },
                ticks: {
                    color: '#6b7280',
                    font: {
                        family: 'Inter',
                        size: 11
                    },
                    padding: 3,
                    callback: function(value) {
                        return value + 'k';
                    }
                }
            }
        },
        elements: {
            point: {
                radius: 4,
                hoverRadius: 6
            },
            line: {
                tension: 0.1
            }
        }
    };
    
    // Gráfico Tesouro Gerencial
    const tesouroGerencialCtx = document.getElementById('tesouroGerencialChart').getContext('2d');
    new Chart(tesouroGerencialCtx, {
        type: 'line',
        data: {
            labels: months,
            datasets: [{
                label: 'SUM (coalesce(siafi_valor_pago, 0))',
                data: tesouroGerencialData,
                borderColor: '#66308F',
                backgroundColor: 'rgba(102, 48, 143, 0.1)',
                borderWidth: 2,
                fill: false,
                pointBackgroundColor: '#ffffff',
                pointBorderColor: '#66308F',
                pointHoverBackgroundColor: '#ffffff',
                pointHoverBorderColor: '#66308F',
                pointRadius: 4,
                pointHoverRadius: 8,
                pointBorderWidth: 2,
                pointHoverBorderWidth: 3
            }]
        },
        options: {
            ...commonOptions,
            plugins: {
                ...commonOptions.plugins,
                tooltip: {
                    enabled: true,
                    backgroundColor: '#66308F',
                    titleColor: '#ffffff',
                    bodyColor: '#ffffff',
                    borderColor: '#66308F',
                    borderWidth: 0,
                    cornerRadius: 6,
                    displayColors: false,
                    titleFont: {
                        family: 'Inter',
                        size: 12,
                        weight: '600'
                    },
                    bodyFont: {
                        family: 'Inter',
                        size: 12,
                        weight: '500'
                    },
                    padding: {
                        top: 8,
                        bottom: 8,
                        left: 12,
                        right: 12
                    },
                    callbacks: {
                        title: function(context) {
                            return context[0].label;
                        },
                        label: function(context) {
                            return new Intl.NumberFormat('pt-BR', { 
                                style: 'currency', 
                                currency: 'BRL',
                                minimumFractionDigits: 0,
                                maximumFractionDigits: 0
                            }).format(context.parsed.y * 1000);
                        }
                    }
                }
            }
        }
    });
    
    // Gráfico ComprasNet
    const comprasNetCtx = document.getElementById('comprasNetChart').getContext('2d');
    new Chart(comprasNetCtx, {
        type: 'line',
        data: {
            labels: months,
            datasets: [
                {
                    label: 'SUM (coalesce(comprasgov_valor_pago, 0))',
                    data: comprasNetPagoData,
                    borderColor: '#9F5528',
                    backgroundColor: 'rgba(159, 85, 40, 0.1)',
                    borderWidth: 2,
                    fill: false,
                    pointBackgroundColor: '#ffffff',
                    pointBorderColor: '#9F5528',
                    pointHoverBackgroundColor: '#ffffff',
                    pointHoverBorderColor: '#9F5528',
                    pointRadius: 4,
                    pointHoverRadius: 8,
                    pointBorderWidth: 2,
                    pointHoverBorderWidth: 3
                },
                {
                    label: 'SUM (coalesce(comprasgov_valor_cronograma, 0))',
                    data: comprasNetCronogramaData,
                    borderColor: '#F59E0B',
                    backgroundColor: 'rgba(245, 158, 11, 0.1)',
                    borderWidth: 2,
                    fill: false,
                    pointBackgroundColor: '#ffffff',
                    pointBorderColor: '#F59E0B',
                    pointHoverBackgroundColor: '#ffffff',
                    pointHoverBorderColor: '#F59E0B',
                    pointRadius: 4,
                    pointHoverRadius: 8,
                    pointBorderWidth: 2,
                    pointHoverBorderWidth: 3
                }
            ]
        },
        options: {
            ...commonOptions,
            plugins: {
                ...commonOptions.plugins,
                tooltip: {
                    enabled: true,
                    backgroundColor: '#F59E0B',
                    titleColor: '#ffffff',
                    bodyColor: '#ffffff',
                    borderColor: '#F59E0B',
                    borderWidth: 0,
                    cornerRadius: 6,
                    displayColors: false,
                    titleFont: {
                        family: 'Inter',
                        size: 12,
                        weight: '600'
                    },
                    bodyFont: {
                        family: 'Inter',
                        size: 12,
                        weight: '500'
                    },
                    padding: {
                        top: 8,
                        bottom: 8,
                        left: 12,
                        right: 12
                    },
                    callbacks: {
                        title: function(context) {
                            return context[0].label;
                        },
                        label: function(context) {
                            return new Intl.NumberFormat('pt-BR', { 
                                style: 'currency', 
                                currency: 'BRL',
                                minimumFractionDigits: 0,
                                maximumFractionDigits: 0
                            }).format(context.parsed.y * 1000);
                        }
                    }
                }
            }
        }
    });
    
}