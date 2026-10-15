"""Add the base-image compatibility reasoning to the new-gates evidence file.

The buyer host is recorded as build 20348 (image-delivery-gate.md), and this task
must also run on Windows 11 hosts. Windows container rules decide which base image
can satisfy both, so the reasoning is recorded verbatim rather than implied.
"""

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
PATH = os.path.join(HERE, "new-gates-evidence.json")

REASONING = [
    "Windows container compatibility: a container image can only start on a host whose build is greater than or equal to the image build. Under process isolation the two builds must match; under Hyper-V isolation the image build may be lower.",
    "Buyer host is build 20348/ltsc2022 (recorded in image-delivery-gate.md), therefore the image build must be <= 20348. windows/server:ltsc2025 is build 26100 and could not start on the buyer host at all, which is why the 'prefer 2025' guidance yields to this hard requirement.",
    "Windows 11 hosts are build 22000 and above. Because 20348 <= 22000, windows/server:ltsc2022 runs on Windows 11 hosts under Hyper-V isolation, so a single image covers both target environments.",
    "This is empirically confirmed on the authoring machine: it is Windows 11 build 26100, and the earlier task runs in this repository used build 20348 images on it successfully.",
    "windows/server:ltsc2022 is a complete, untrimmed system (two layers, 4176 MB) and is not one of the forbidden trimmed families; windows/servercore:ltsc2022 (2066 MB) and windows/nanoserver:ltsc2022 (116 MB) are forbidden by current-project-policy.md item 1.",
    "No Windows 11 client container image exists on mcr: the windows repository client line stops at Windows 10 20H2 and has no 21H2/22H2/23H2/24H2/ltsc2024 tag, so 'use a Windows 11 container image' is not an available option.",
]


def main():
    with open(PATH, "r", encoding="utf-8") as handle:
        doc = json.load(handle)

    doc["image_delivery"]["target_compatibility_reasoning"] = REASONING
    doc["image_delivery"]["target_profile"]["windows_build"] = 20348
    doc["image_delivery"]["target_profile"]["windows_11_compatible_via"] = "hyperv-isolation"

    doc["windows_image_policy"]["notes"] = [
        "Buyer host build is 20348/ltsc2022, so the image build must not exceed 20348; ltsc2025 (26100) cannot start there.",
        "Windows 11 hosts are 22000+, and 20348 <= 22000, so this image also runs there under Hyper-V isolation. One image covers both targets.",
        "The image is the complete untrimmed Windows Server family, so it is not subject to the Nano Server / Server Core prohibition.",
        "ltsc2022 is not the 'prefer 2025' choice; it is the compliant choice because buyer runnability is a hard gate and the policy says to pick a compatible complete image and record the basis.",
    ]

    with open(PATH, "w", encoding="utf-8") as handle:
        json.dump(doc, handle, ensure_ascii=False, indent=2)

    print("updated:", PATH)
    print("  target_profile:", json.dumps(doc["image_delivery"]["target_profile"], ensure_ascii=False))
    print("  reasoning items:", len(REASONING))


if __name__ == "__main__":
    main()
