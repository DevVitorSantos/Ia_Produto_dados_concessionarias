from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.feedback_store import FeedbackStore
from services.profile_store import ProfileStore


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Cria o dataset analytics_ops, as tabelas de perfil/eventos/feedback e a view de leitura."
    )
    parser.add_argument("--dataset", default=None, help="Dataset de destino; padrão analytics_ops.")
    parser.add_argument(
        "--service-account",
        default=None,
        help="Caminho opcional para credencial com permissão de criação de dataset/tabelas.",
    )
    args = parser.parse_args()

    if args.service_account:
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = args.service_account

    store = FeedbackStore(dataset_id=args.dataset)
    store.ensure_tables()
    profiles = ProfileStore(dataset_id=args.dataset)
    profiles.ensure_table()
    print(
        f"Dataset/tabelas prontos: {store.events_table_id()}, {store.feedback_table_id()} "
        f"e {profiles.table_id()}. View pronta: {store.view_id()}"
    )


if __name__ == "__main__":
    main()
