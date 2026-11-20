import json

from services.openai_service import OpenAIService


def main() -> None:
    answer = OpenAIService().ask("Qual foi o faturamento total da base?")
    print(json.dumps(answer.to_dict(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
