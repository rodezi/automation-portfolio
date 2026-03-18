import argparse
import asyncio

from scraper import scrape_google_maps

DEFAULT_QUERIES = [
    "desarrolladora inmobiliaria Ciudad de Mexico",
    "inmobiliaria Ciudad de Mexico",
    "real estate agency Ciudad de Mexico",
    "constructora inmobiliaria CDMX",
    "agencia inmobiliaria CDMX",
]


def parse_args():
    parser = argparse.ArgumentParser(
        description="Google Maps scraper — Inmobiliarias / Real Estate"
    )
    parser.add_argument(
        "-q", "--queries",
        nargs="+",
        default=None,
        help=(
            'Términos de búsqueda. Ej: -q "inmobiliaria Monterrey" "real estate Guadalajara". '
            "Si no se especifica, usa las búsquedas predeterminadas."
        ),
    )
    parser.add_argument(
        "-o", "--output",
        default="results.csv",
        help="Archivo CSV de salida (default: results.csv)",
    )
    parser.add_argument(
        "-n", "--max-results",
        type=int,
        default=100,
        help="Máximo de resultados por búsqueda (default: 100)",
    )
    parser.add_argument(
        "--no-headless",
        action="store_true",
        help="Mostrar el navegador (útil para depuración)",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    queries = args.queries or DEFAULT_QUERIES

    print("=" * 60)
    print("  Google Maps Scraper — Inmobiliarias / Real Estate")
    print("=" * 60)
    print(f"Búsquedas: {len(queries)}")
    print(f"Max por búsqueda: {args.max_results}")
    print(f"Salida: {args.output}")
    print(f"Headless: {not args.no_headless}")
    print("=" * 60)

    asyncio.run(
        scrape_google_maps(
            queries=queries,
            output_file=args.output,
            max_results=args.max_results,
            headless=not args.no_headless,
        )
    )


if __name__ == "__main__":
    main()
