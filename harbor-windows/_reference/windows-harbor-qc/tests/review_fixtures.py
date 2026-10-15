"""Evidence-schema unit fixtures; these are not real image/installation evidence."""
from windows_image_policy import windows_image_template, tools_template
from nested_virtualization_review import NESTED_CHECKS, nested_virtualization_template


def passing_windows_image(image):
    result = windows_image_template()
    result.update(status="PASS", evidence=["fixture/image-inspect.json", "fixture/image-lineage.json"],
                  configured_image=image, windows_build=20348, release_year=2022,
                  family="windows-server", untrimmed=True,
                  runtime_bases=[{
                      "image": "fixture.example/windows-server:2022", "windows_build": 20348,
                      "release_year": 2022, "family": "windows-server", "untrimmed": True,
                      "evidence": ["fixture/base-inspect.json", "fixture/base-source.md"],
                  }])
    return result


def passing_tools():
    result = tools_template()
    result.update(status="PASS", evidence=["fixture/tool-inventory.md"], tools=[{
        "name": "PowerShell", "version": "5.1", "required_by": "tests/test.ps1",
        "dockerfile_location": "environment/Dockerfile:12; RUN explicit tool validation",
        "provisioning_kind": "base_inherited", "provisioning_evidence": ["fixture/build.log"],
        "functional_probe": "fixture command and assertion for task-specific Win32 call",
        "runtime_evidence": ["fixture/functional-probe.log"], "status": "PASS",
    }])
    return result


def passing_nested_virtualization(image, identity=None):
    result = nested_virtualization_template()
    result.update(status="PASS", evidence=["fixture/nested-review.md"], configured_image=image,
                  task_id="demo", task_version="1.0.0", task_hash="a" * 64,
                  virtualization_depth=2, outer_guest_id="fixture-guest-l1",
                  outer_hypervisor="fixture outer hypervisor", inner_hypervisor="fixture inner Hyper-V",
                  virtualization_extensions_exposed=True, inner_virtualization_enabled=True,
                  task_runtime_in_nested_layer=True)
    if identity:
        for field in ("task_id", "task_version", "task_hash"):
            result[field] = identity[field]
    result["checks"] = {
        key: {"status": "PASS", "evidence": [f"fixture/{key}.log"],
              "notes": "unit fixture; topology and execution must be examined in real QC"}
        for key in NESTED_CHECKS
    }
    return result
