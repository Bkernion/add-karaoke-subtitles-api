#!/usr/bin/env python3
"""
Download Google Fonts for artistic video generation.

This script downloads TTF font files from Google Fonts API and saves them
to the fonts/ directory for use in the artistic word-by-word video generator.
"""

import os
import sys
import urllib.request
import urllib.error
import zipfile
import io
import shutil
from pathlib import Path


# Font configurations: (font_family, variant/weight to download)
# Some fonts only have regular weight, others have specific weights we want
FONTS_TO_DOWNLOAD: list[tuple[str, str]] = [
    # Bold/Impact Fonts
    ("Bebas Neue", "regular"),
    ("Oswald", "700"),  # Bold weight
    ("Anton", "regular"),
    ("Archivo Black", "regular"),
    ("Passion One", "regular"),
    ("Montserrat", "700"),  # Bold weight
    ("Poppins", "700"),  # Bold weight
    ("Rubik", "700"),  # Bold weight
    ("Raleway", "900"),  # Black weight
    ("Quicksand", "700"),  # Bold weight
    # Fun/Playful Fonts
    ("Permanent Marker", "regular"),
    ("Lobster", "regular"),
    ("Bangers", "regular"),
    ("Righteous", "regular"),
    ("Fredoka One", "regular"),
    ("Luckiest Guy", "regular"),
    ("Boogaloo", "regular"),
    ("Titan One", "regular"),
    # Script/Handwritten Fonts
    ("Pacifico", "regular"),
    ("Caveat", "700"),  # Bold weight for better readability
    ("Kaushan Script", "regular"),
    ("Rock Salt", "regular"),
    ("Shadows Into Light", "regular"),
    # Stylized/Unique Fonts
    ("Black Ops One", "regular"),
    ("Russo One", "regular"),
]


def get_font_download_url(font_family: str) -> str:
    """
    Get the Google Fonts download URL for a font family.

    Args:
        font_family: The name of the font family

    Returns:
        URL to download the font ZIP file
    """
    # Google Fonts download URL format
    # Spaces in font names are replaced with +
    font_name_encoded = font_family.replace(" ", "+")
    return f"https://fonts.google.com/download?family={font_name_encoded}"


def download_font(font_family: str, weight: str, fonts_dir: Path) -> bool:
    """
    Download a font from Google Fonts and extract the TTF file.

    Args:
        font_family: The name of the font family
        weight: The weight/variant to use (e.g., "regular", "700")
        fonts_dir: Directory to save the font file

    Returns:
        True if download was successful, False otherwise
    """
    url = get_font_download_url(font_family)

    print(f"Downloading {font_family}...")

    try:
        # Download the ZIP file
        request = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (compatible; FontDownloader/1.0)"}
        )
        response = urllib.request.urlopen(request, timeout=30)
        zip_data = response.read()

        # Extract TTF files from ZIP
        with zipfile.ZipFile(io.BytesIO(zip_data)) as zf:
            # Find the TTF file matching our weight preference
            ttf_files = [f for f in zf.namelist() if f.endswith(".ttf")]

            if not ttf_files:
                print(f"  Warning: No TTF files found for {font_family}")
                return False

            # Try to find the specific weight we want
            target_file = None

            # Build search patterns for the weight
            weight_patterns = []
            if weight == "regular":
                weight_patterns = ["Regular", "regular", "-Regular", "_Regular"]
            else:
                weight_patterns = [weight, f"-{weight}", f"_{weight}"]
                # Also check for weight names
                weight_names: dict[str, list[str]] = {
                    "700": ["Bold", "bold", "-Bold", "_Bold"],
                    "900": ["Black", "black", "-Black", "_Black", "ExtraBold", "extrabold"],
                }
                if weight in weight_names:
                    weight_patterns.extend(weight_names[weight])

            # Search for matching file
            for ttf in ttf_files:
                ttf_lower = ttf.lower()
                for pattern in weight_patterns:
                    if pattern.lower() in ttf_lower:
                        target_file = ttf
                        break
                if target_file:
                    break

            # If no specific match, use the first TTF (often there's only one)
            if not target_file:
                # For single-weight fonts, just use the first TTF
                target_file = ttf_files[0]

            # Create output filename (sanitized)
            safe_name = font_family.replace(" ", "")
            output_name = f"{safe_name}.ttf"
            output_path = fonts_dir / output_name

            # Extract the file
            with zf.open(target_file) as src:
                with open(output_path, "wb") as dst:
                    dst.write(src.read())

            print(f"  Saved: {output_name}")
            return True

    except urllib.error.URLError as e:
        print(f"  Error downloading {font_family}: {e}")
        return False
    except zipfile.BadZipFile:
        print(f"  Error: Invalid ZIP file for {font_family}")
        return False
    except Exception as e:
        print(f"  Error processing {font_family}: {e}")
        return False


def main() -> int:
    """
    Main function to download all fonts.

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    # Determine the fonts directory
    script_dir = Path(__file__).parent
    fonts_dir = script_dir / "fonts"

    # Create fonts directory if it doesn't exist
    fonts_dir.mkdir(exist_ok=True)

    print(f"Downloading {len(FONTS_TO_DOWNLOAD)} fonts to {fonts_dir}")
    print("-" * 50)

    successful = 0
    failed = 0

    for font_family, weight in FONTS_TO_DOWNLOAD:
        if download_font(font_family, weight, fonts_dir):
            successful += 1
        else:
            failed += 1

    print("-" * 50)
    print(f"Download complete: {successful} successful, {failed} failed")

    if failed > 0:
        print("\nNote: Some fonts failed to download. You may need to download them manually.")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
