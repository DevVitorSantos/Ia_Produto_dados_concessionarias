import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.bigquery_service import BigQueryService


def main() -> None:
    service = BigQueryService()
    results = service.run_smoke_checks()

    print("Conexão:", results["conexao"])
    print("Objetos Gold:", [row["table_name"] for row in results["objetos_gold"]])
    print("Vendas:", results["vendas"])
    print("Por ano:", results["por_ano"])
    print("Desconto:", results["desconto"])
    print("Chaves:", results["chaves"])


if __name__ == "__main__":
    main()
