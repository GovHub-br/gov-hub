FROM apache/airflow:3.2.2-python3.11

USER root
RUN apt-get update \
  && apt-get install -y --no-install-recommends \
         build-essential \
         libgtk2.0-dev \
         libgdal-dev \
         unixodbc-dev \
         libpq-dev \
         vim \
         unzip \
         git \
         curl \
  && sed -i 's,^\(MinProtocol[ ]*=\).*,\1'TLSv1.0',g' /etc/ssl/openssl.cnf \
  && sed -i 's,^\(CipherString[ ]*=\).*,\1'DEFAULT@SECLEVEL=1',g' /etc/ssl/openssl.cnf \
  && curl -O http://acraiz.icpbrasil.gov.br/credenciadas/CertificadosAC-ICP-Brasil/ACcompactado.zip \
  && unzip -o ACcompactado.zip -d /usr/local/share/ca-certificates/ \
  && update-ca-certificates \
  && apt-get autoremove -yqq --purge \
  && apt-get clean \
  && rm -rf \
    /var/lib/apt/lists/* \
    /tmp/* \
    /var/tmp/* \
    /usr/share/man \
    /usr/share/doc \
    /usr/share/doc-base \
  && sed -i 's/^# en_US.UTF-8 UTF-8$/en_US.UTF-8 UTF-8/g' /etc/locale.gen \
  && sed -i 's/^# pt_BR.UTF-8 UTF-8$/pt_BR.UTF-8 UTF-8/g' /etc/locale.gen \
  && locale-gen en_US.UTF-8 pt_BR.UTF-8 \
  && update-locale LANG=en_US.UTF-8 LC_ALL=en_US.UTF-8

USER airflow
WORKDIR ${AIRFLOW_HOME}

# Para rodar o airflow só precisamos instalar as dependências visto que o código
# sempre será sincronizado via git sync ou via volumes localmente
COPY --from=ghcr.io/astral-sh/uv:0.12.9 /uv /usr/local/bin/uv

COPY requirements.txt .
# `uv pip` no lugar do pip: mesma resolucao a partir do requirements.txt ja
# pinado, porem varias vezes mais rapido.
#
# --python e obrigatorio aqui, nao e preferencia. A imagem do Airflow instala
# tudo em /home/airflow/.local, que e um venv de verdade (tem pyvenv.cfg) e e
# o sys.prefix do interpretador. Sem apontar para ele, o uv tenta o Python do
# sistema em /usr/python e falha com "Permission denied", porque este estagio
# roda como o usuario airflow.
RUN uv pip install --python /home/airflow/.local/bin/python --no-cache -r requirements.txt
