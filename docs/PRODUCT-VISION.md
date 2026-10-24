# What I want Ternuxx to become

I want my phone to be a world-class mobile workstation I can carry in my pocket. Ternuxx runs directly in Native Termux on Android and uses the CPU as its baseline, with GPU or NPU acceleration only when a named workload proves it works on my device.

Ternuxx owns Native boot/recovery, SSH, CLI, management, state, desktop, and host workloads. Debian PRoot is an optional isolated workload provider managed from the Native host. The separate Ternux repository and launcher remain independent and are not modified by Ternuxx.

I want four easy ways to manage the same Native workstation: CLI, an interactive Terminal/TUI, Web UI, and Graphical UI. Each client calls the same management service and operation contract, so validation, authorization, state, journaling, and recovery behave consistently. Keep the help and interactive guidance simple to follow.

I want the documentation and compatibility research reviewed before feature changes. Keep Native runtime evidence distinct from dated historical PRoot evidence, owner reports, and untested proposals. Do not claim GPU/NPU acceleration from a device node, library, or renderer string alone. Keep device checks read-only unless I explicitly authorize a specific change.
