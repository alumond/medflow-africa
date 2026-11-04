"""Run with: python -m scripts.generate_demo_data."""

from app.data.generate import write_demo

if __name__ == "__main__":
    write_demo()
    print("Generated four reproducible CSV files and a separate scenario manifest in data/demo/.")
