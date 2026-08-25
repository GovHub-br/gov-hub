import logging
import io
import smtplib
import zipfile
from email.message import EmailMessage
from mimetypes import guess_type
from typing import Mapping, Optional, List, Dict
import pandas as pd
from pandas.errors import EmptyDataError
from imap_tools import MailBox, AND
import chardet
from datetime import datetime, date
import pytz

# Configuração do log
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


def format_csv(
    csv_data: str,
    column_mapping: Optional[Dict[int, str]],
    skiprows: int,
    delimiter: Optional[str] = None,
) -> pd.DataFrame:
    """Formata um arquivo CSV conforme mapeamento de colunas."""
    read_csv_kwargs = {"sep": delimiter} if delimiter else {}
    if column_mapping:
        df = pd.read_csv(
            io.StringIO(csv_data),
            skiprows=skiprows,
            header=None,
            **read_csv_kwargs,
        )
        column_names: List[str] = [
            column_mapping.get(i, f"col_{i}") for i in range(len(df.columns))
        ]
        df.columns = pd.Index(column_names)
    else:
        df = pd.read_csv(
            io.StringIO(csv_data), skiprows=skiprows, header=0, **read_csv_kwargs
        )
    return df


def extract_csv_from_zip(
    zip_payload: bytes,
    column_mapping: dict | None,
    skiprows: int = 0,
    delimiter: Optional[str] = None,
) -> Optional[pd.DataFrame]:
    """Extrai e formata o primeiro arquivo CSV encontrado em um ZIP."""
    with zipfile.ZipFile(io.BytesIO(zip_payload)) as zip_file:
        for file_name in zip_file.namelist():
            if file_name.lower().endswith(".csv"):
                raw_data = zip_file.read(file_name)
                encoding = chardet.detect(raw_data)["encoding"]

                if not raw_data.strip():
                    logging.warning("CSV vazio no anexo ZIP: %s", file_name)
                    continue

                try:
                    decoded_data = raw_data.decode(encoding or "utf-8", errors="replace")
                    if not decoded_data.strip():
                        logging.warning("CSV vazio no anexo ZIP: %s", file_name)
                        continue
                    return format_csv(decoded_data, column_mapping, skiprows, delimiter)
                except EmptyDataError:
                    logging.warning(
                        "CSV sem colunas apos skiprows=%s no arquivo: %s",
                        skiprows,
                        file_name,
                    )
                    continue
    return None


def fetch_email_with_zip(
    imap_server: str,
    email: str,
    password: str,
    sender_email: str,
    subject: Optional[str],
    target_date: Optional[date] = None,
    subject_suffix: Optional[str] = None,
) -> List[bytes]:
    """Busca e-mails da data alvo (ou dia atual) e retorna os anexos ZIP."""
    if not subject and not subject_suffix:
        raise ValueError("subject ou subject_suffix precisa ser informado.")

    query_date = target_date or datetime.now(pytz.timezone("America/Sao_Paulo")).date()
    zip_payloads: List[bytes] = []
    with MailBox(imap_server).login(email, password) as mailbox:
        # bulk=True: single IMAP FETCH command for all messages (avoids overquota)
        if subject_suffix:
            for msg in mailbox.fetch(
                AND(date=query_date, from_=sender_email),
                bulk=True,
            ):
                msg_subject = msg.subject or ""
                if msg_subject.endswith(subject_suffix):
                    for attachment in msg.attachments:
                        if attachment.filename.lower().endswith(".zip"):
                            zip_payloads.append(attachment.payload)
        else:
            for msg in mailbox.fetch(
                AND(date=query_date, from_=sender_email, subject=subject),
                bulk=True,
            ):
                for attachment in msg.attachments:
                    if attachment.filename.lower().endswith(".zip"):
                        zip_payloads.append(attachment.payload)
    return zip_payloads


def fetch_email_with_csv(
    imap_server: str, email: str, password: str, sender_email: str, subject: str
) -> List[bytes]:
    """Busca todos os e-mails do dia atual e retorna anexos CSV diretos."""
    today = datetime.now(pytz.timezone("America/Sao_Paulo")).date()
    csv_payloads: List[bytes] = []
    with MailBox(imap_server).login(email, password) as mailbox:
        # bulk=True: single IMAP FETCH command for all messages (avoids overquota)
        for msg in mailbox.fetch(
            AND(date=today, from_=sender_email, subject=subject), bulk=True
        ):
            for attachment in msg.attachments:
                file_name = (attachment.filename or "").lower()
                if file_name.endswith(".csv"):
                    csv_payloads.append(attachment.payload)
    return csv_payloads


def extract_csv_from_payload(
    payload: bytes, column_mapping: dict, skiprows: int = 0
) -> Optional[pd.DataFrame]:
    """Decodifica payload CSV e aplica formatação padrão."""
    if not payload.strip():
        logging.warning("Anexo CSV vazio.")
        return None

    encoding = chardet.detect(payload)["encoding"]
    decoded_data = payload.decode(encoding or "utf-8", errors="replace")
    if not decoded_data.strip():
        logging.warning("Anexo CSV vazio apos decodificacao.")
        return None

    try:
        return format_csv(decoded_data, column_mapping, skiprows)
    except EmptyDataError:
        logging.warning("CSV sem colunas apos skiprows=%s.", skiprows)
        return None


def fetch_and_process_email(
    imap_server: str,
    email: str,
    password: str,
    sender_email: str,
    subject: str,
    column_mapping: dict | None,
    skiprows: int = 0,
    target_date: Optional[date] = None,
    delimiter: Optional[str] = None,
) -> Optional[str]:
    """Busca e processa e-mails da data alvo (ou dia atual), extraindo CSVs."""
    try:
        zip_payloads = fetch_email_with_zip(
            imap_server,
            email,
            password,
            sender_email,
            subject,
            target_date=target_date,
        )
        if not zip_payloads:
            logging.warning("Nenhum anexo ZIP encontrado.")
            return None

        logging.info("Total de anexos ZIP encontrados: %s", len(zip_payloads))

        dataframes: List[pd.DataFrame] = []
        for idx, zip_payload in enumerate(zip_payloads, start=1):
            csv_data = extract_csv_from_zip(
                zip_payload, column_mapping, skiprows, delimiter
            )
            if csv_data is not None:
                dataframes.append(csv_data)
            else:
                logging.warning(
                    "ZIP %s ignorado por nao conter CSV valido.",
                    idx,
                )

        if dataframes:
            combined_df = pd.concat(dataframes, ignore_index=True)
            return combined_df.to_csv(index=False)

        logging.warning("Nenhum CSV processado.")
    except Exception as e:
        logging.error(f"Erro ao processar e-mails: {e}")
        raise


def fetch_and_process_email_csv_attachment(
    imap_server: str,
    email: str,
    password: str,
    sender_email: str,
    subject: str,
    column_mapping: dict,
    skiprows: int = 0,
) -> Optional[str]:
    """Busca e processa e-mails do dia, extraindo CSVs anexados diretamente."""
    try:
        csv_payloads = fetch_email_with_csv(
            imap_server, email, password, sender_email, subject
        )
        if not csv_payloads:
            logging.warning("Nenhum anexo CSV encontrado.")
            return None

        logging.info("Total de anexos CSV encontrados: %s", len(csv_payloads))

        dataframes: List[pd.DataFrame] = []
        for idx, payload in enumerate(csv_payloads, start=1):
            csv_data = extract_csv_from_payload(payload, column_mapping, skiprows)
            if csv_data is not None:
                dataframes.append(csv_data)
            else:
                logging.warning(
                    "CSV %s ignorado por nao conter dados validos.",
                    idx,
                )

        if dataframes:
            combined_df = pd.concat(dataframes, ignore_index=True)
            return combined_df.to_csv(index=False)

        logging.warning("Nenhum CSV processado.")
        return None
    except Exception as e:
        logging.error(f"Erro ao processar e-mails com CSV direto: {e}")
        raise


def enviar_email(
    credenciais: Mapping[str, object],
    destinatarios: List[str],
    assunto: str,
    corpo: str,
    anexos: Optional[List[tuple]] = None,
) -> None:
    """Envia um e-mail com anexos via SMTP (ADR-0019).

    `credenciais` é o JSON da Variable de SMTP do Airflow, com as chaves
    `host`, `port`, `usuario`, `senha`, `remetente` e, opcionalmente, `tls`
    (padrão: True). Os destinatários vão em cópia oculta: um relatório enviado
    a vários órgãos não expõe a lista de endereços de todos eles, que é dado
    pessoal (ADR-0013).
    """
    if not destinatarios:
        logging.warning("[cliente_email] Nenhum destinatário; envio ignorado.")
        return

    remetente = str(credenciais.get("remetente") or credenciais.get("usuario") or "")
    if not remetente:
        raise ValueError("Credenciais de SMTP sem 'remetente' nem 'usuario'.")

    mensagem = EmailMessage()
    mensagem["From"] = remetente
    mensagem["To"] = remetente
    mensagem["Bcc"] = ", ".join(destinatarios)
    mensagem["Subject"] = assunto
    mensagem.set_content(corpo)

    for nome, conteudo in anexos or []:
        tipo, _ = guess_type(nome)
        principal, _, secundario = (tipo or "application/octet-stream").partition("/")
        mensagem.add_attachment(
            conteudo,
            maintype=principal,
            subtype=secundario or "octet-stream",
            filename=nome,
        )

    host = str(credenciais.get("host") or "")
    porta = int(str(credenciais.get("port") or 587))
    usuario = str(credenciais.get("usuario") or "")
    senha = str(credenciais.get("senha") or "")
    usar_tls = bool(credenciais.get("tls", True))

    with smtplib.SMTP(host, porta, timeout=60) as servidor:
        if usar_tls:
            servidor.starttls()
        if usuario and senha:
            servidor.login(usuario, senha)
        servidor.send_message(mensagem)

    logging.info(
        "[cliente_email] Relatório enviado para %s destinatário(s): %s",
        len(destinatarios),
        assunto,
    )
