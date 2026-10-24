# Ternuxx documentation index

Use this page to find the current product, operating, architecture, testing, audit, and release-readiness documentation. The live phase status is generated from `project/phase-state.json`; dated evidence records what was observed at the time named in each file.

## Start here

- [Product vision](PRODUCT-VISION.md)
- [English quick start](../README.md)
- [বাংলা পরিচিতি](../bn/README.md) · [বাংলা ইনস্টল নির্দেশিকা](../bn/INSTALLATION.md)
- [Installation and upgrade](INSTALLATION.md)
- [Operations and command reference](OPERATIONS.md)
- [Architecture](ARCHITECTURE.md)
- [Roadmap and phase gates](ROADMAP.md)
- [Current phase status](PHASE-STATUS.md)

## Native workloads

- [Native graphics and audio](architecture/NATIVE-GRAPHICS-AUDIO.md)
- [Software catalog](SOFTWARE-CATALOG.md)
- [Optimization guide](OPTIMIZATION.md)
- [Wine/Hangover research (not implemented)](WINE-NATIVE.md)

## Debian PRoot workloads

- [PRoot restoration and live acceptance](evidence/2026-10-24-p11-proot-source-restoration-audit.md)
- [PRoot graphics evidence](PROOT-GPU.md)
- [PRoot operations](OPERATIONS.md#proot-and-debian)

## Architecture and interfaces

- [Shared capability matrix](architecture/CAPABILITY-MATRIX.md)
- [Management API](architecture/MANAGEMENT-API.md)
- [SSH lifecycle](architecture/SSH-LIFECYCLE.md)
- [Architecture decisions](architecture/decisions/)

## Historical and superseded material

The temporary Native-only decision is documented in dated history and superseded by the owner's PRoot reauthorization on 2026-10-24. Archived [roadmap](history/ROADMAP-pre-native-only-2026-10-24.md), [management API contract](history/MANAGEMENT-API-pre-native-only-2026-10-24.md), [feature matrix](history/FEATURE-MATRIX-pre-native-only-2026-10-17.yaml), and [software catalog](history/SOFTWARE-CATALOG-pre-native-only-2026-10-24.md) remain snapshots; they do not describe current supported behavior.

Older design-only references remain historical: [hybrid integration](HYBRID-INTEGRATION.md), [PRoot GUI display experiment](PROOT-GUI-DISPLAY0.md), [shared-X11 PRoot applications](PROOT-SHARED-X11.md), [interactive guest terminals](architecture/INTERACTIVE-PROOT-TERMINALS.md), and the [pre-migration reboot guide](history/REBOOT-RECOVERY-GUIDE-pre-native-only-2026-10-24.md). Check P11 and the capability matrix before relying on any dated behavior.

## Testing and evidence

- [Testing and qualification](testing/README.md)
- [Native reboot and recovery](testing/REBOOT-RECOVERY-GUIDE.md)
- [Known limitations](testing/KNOWN-LIMITATIONS.md)
- [CPU baseline](testing/CPU-BASELINE.md)
- [GPU qualification](testing/GPU-ACCELERATION.md)
- [NPU qualification](testing/NPU-ACCELERATION.md)
- [P12 Mesa source license-header inventory](evidence/2026-10-24-p12-mesa-source-license-inventory.md)
- [Device compatibility](testing/DEVICE-COMPATIBILITY.md) · [Current capability matrix](testing/FEATURE-MATRIX.yaml)
- [Dated evidence](evidence/) · [Device test reports](testing/reports/)

## Project maintenance

- [Current repository audit and remaining gates](audit/REPOSITORY-AUDIT.md)
- [Phase revalidation](audit/PHASE-REVALIDATION.md)
- [Knowledge synchronization](KNOWLEDGE-SYNC.md)
- [Security policy](../SECURITY.md)
- [License and release readiness](readiness/README.md)
- [Third-party artifact notices](readiness/THIRD-PARTY-NOTICES.md)
