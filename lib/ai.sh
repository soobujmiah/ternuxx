#!/data/data/com.termux/files/usr/bin/bash

# Native CPU inference command. The shared management service owns operation
# validation; the Termux package manager continues to own llama-cpp.
nt_cmd_ai() {
  nt_require_termux || return $?
  local service="${_TN_LIB_DIR}/management_service.py" sub="${1:-status}"
  [ "$#" -gt 0 ] && shift || true
  case "$sub" in
    runtime)
      local backend="cpu" package="llama-cpp"
      [ "${1:-}" = preview ] && shift || { nt_fail "Usage: tx ai runtime preview [cpu|vulkan|opencl]"; return 2; }
      [ "$#" -le 1 ] || { nt_fail "Usage: tx ai runtime preview [cpu|vulkan|opencl]"; return 2; }
      [ "$#" -eq 0 ] || backend="$1"
      case "$backend" in
        cpu) ;;
        vulkan) package="llama-cpp llama-cpp-backend-vulkan" ;;
        opencl) package="llama-cpp llama-cpp-backend-opencl" ;;
        *) nt_fail "Backend must be cpu, vulkan, or opencl."; return 2 ;;
      esac
      command -v apt-get >/dev/null 2>&1 || { nt_fail "Termux apt-get is unavailable."; return 2; }
      printf '%s\n' "Read-only Termux package simulation for Native llama.cpp ($backend):"
      # Word splitting is intentional: package is built only from the fixed allowlist above.
      apt-get -s install $package
      ;;
    status)
      [ "$#" -eq 0 ] || { nt_fail "Usage: tx ai status"; return 2; }
      python3 "$service" --operation inference.cpu.status --json
      ;;
    devices)
      [ "$#" -eq 0 ] || { nt_fail "Usage: tx ai devices"; return 2; }
      python3 "$service" --operation inference.gpu.status --json
      ;;
    npu)
      local action="${1:-status}"
      [ "$#" -gt 0 ] && shift || true
      case "$action" in
        status)
          [ "$#" -eq 0 ] || { nt_fail "Usage: tx ai npu status"; return 2; }
          python3 "$service" --operation inference.npu.status --json
          ;;
        runtime)
          local runtime_action="${1:-}"
          [ "$#" -gt 0 ] && shift || true
          case "$runtime_action" in
            preview)
              [ "$#" -eq 0 ] || { nt_fail "Usage: tx ai npu runtime preview"; return 2; }
              python3 "$service" --operation inference.npu.runtime.preview --json
              ;;
            apply)
              local plan_id="" confirm=""
              while [ "$#" -gt 0 ]; do
                case "$1" in
                  --plan-id) [ "$#" -ge 2 ] || { nt_fail "--plan-id requires a preview ID"; return 2; }; plan_id="$2"; shift 2 ;;
                  --confirm) [ "$#" -ge 2 ] || { nt_fail "--confirm requires INSTALL"; return 2; }; confirm="$2"; shift 2 ;;
                  *) nt_fail "Unknown NPU runtime option: $1"; return 2 ;;
                esac
              done
              if [ -z "$plan_id" ] && [ -t 0 ]; then
                local preview_json
                preview_json="$(python3 "$service" --operation inference.npu.runtime.preview --json)" || return $?
                printf '%s\n' "$preview_json"
                plan_id="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["data"]["plan_id"])' <<<"$preview_json")" || return 2
                read -r -p 'Type INSTALL to fetch and verify this exact runtime: ' confirm
              fi
              [ -n "$plan_id" ] || { nt_fail "Run 'tx ai npu runtime preview' and pass its --plan-id."; return 2; }
              python3 "$service" --operation inference.npu.runtime.apply --plan-id "$plan_id" \
                --runtime-confirm "$confirm" --json
              ;;
            *) nt_fail "Usage: tx ai npu runtime {preview|apply}"; return 2 ;;
          esac
          ;;
        *) nt_fail "Usage: tx ai npu {status|runtime preview|runtime apply}"; return 2 ;;
      esac
      ;;
    model)
      local action="${1:-}"
      [ "$#" -gt 0 ] && shift || true
      case "$action" in
        preview|remove-preview)
          [ "$#" -eq 0 ] || { nt_fail "Usage: tx ai model $action"; return 2; }
          local model_action=install
          [ "$action" = remove-preview ] && model_action=remove
          python3 "$service" --operation inference.cpu.model.preview \
            --model-action "$model_action" --json
          ;;
        install|remove)
          local model_action="$action" plan_id="" confirm=""
          while [ "$#" -gt 0 ]; do
            case "$1" in
              --plan-id) [ "$#" -ge 2 ] || { nt_fail "--plan-id requires a preview ID"; return 2; }; plan_id="$2"; shift 2 ;;
              --confirm) [ "$#" -ge 2 ] || { nt_fail "--confirm requires exact DOWNLOAD or REMOVE"; return 2; }; confirm="$2"; shift 2 ;;
              *) nt_fail "Unknown model option: $1"; return 2 ;;
            esac
          done
          if [ -z "$plan_id" ] && [ -t 0 ]; then
            local preview_json
            preview_json="$(python3 "$service" --operation inference.cpu.model.preview \
              --model-action "$model_action" --json)" || return $?
            printf '%s\n' "$preview_json"
            plan_id="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["data"]["plan_id"])' <<<"$preview_json")" || return 2
            if [ "$model_action" = install ]; then
              read -r -p 'Type DOWNLOAD to confirm model file installation: ' confirm
            else
              read -r -p 'Type REMOVE to confirm model file removal: ' confirm
            fi
          fi
          [ -n "$plan_id" ] || { nt_fail "Run 'tx ai model preview' first and pass its --plan-id."; return 2; }
          python3 "$service" --operation inference.cpu.model.apply \
            --model-action "$model_action" --plan-id "$plan_id" \
            --model-confirm "$confirm" --json
          ;;
        *) nt_fail "Usage: tx ai model {preview|install|remove-preview|remove}"; return 2 ;;
      esac
      ;;
    setup)
      if [ "$TERNUXX_JSON" = "1" ]; then
        nt_json_object "ok" "false" "error" "interactive setup requires a terminal" "code" "interactive_required"
        return 2
      fi
      local status_json runtime_available
      status_json="$(python3 "$service" --operation inference.cpu.status --json)" || return $?
      printf '%s\n' "$status_json"
      runtime_available="$(python3 -c 'import json,sys; print("yes" if json.load(sys.stdin)["data"]["runtime"]["available"] else "no")' <<<"$status_json")" || return 2
      if [ "$runtime_available" != yes ]; then
        printf '%s\n' "The llama-cpp runtime is missing. Review the Termux package transaction with \`apt-get -s install llama-cpp\`; if you choose to install it, run \`tx ai setup\` again afterward. Ternuxx does not install packages."
        return 0
      fi
      if [ -t 0 ]; then
        read -r -p 'Review and download the pinned Qwen3 0.6B CPU model? [y/N] ' answer || return 2
        case "$answer" in y|Y|yes|YES) nt_cmd_ai model install || return $? ;; *) return 0 ;; esac
        read -r -p 'Run a local prompt using HTP0, then Vulkan, then CPU fallback? [y/N] ' answer || return 2
        case "$answer" in y|Y|yes|YES) nt_cmd_ai run ;; *) return 0 ;; esac
      else
        nt_fail "Interactive setup needs a terminal; use 'tx ai model preview' for a read-only plan."
        return 2
      fi
      ;;
    run)
      local max_tokens=64 backend=auto device_id="" operation option prompt
      local -a inference_args=()
      while [ "$#" -gt 0 ]; do
        option="$1"; shift
        case "$option" in
          --max-tokens) [ "$#" -gt 0 ] || { nt_fail "--max-tokens needs a number"; return 2; }; max_tokens="$1"; shift ;;
          --backend) [ "$#" -gt 0 ] || { nt_fail "--backend needs cpu, vulkan, or npu"; return 2; }; backend="$1"; shift ;;
          --device) [ "$#" -gt 0 ] || { nt_fail "--device needs the exact listed Vulkan device ID"; return 2; }; device_id="$1"; shift ;;
          *) nt_fail "Prompt is read from stdin; unknown run option: $option"; return 2 ;;
        esac
      done
      case "$backend" in auto) operation=inference.auto.run ;; cpu) operation=inference.cpu.run ;; vulkan) operation=inference.gpu.run ;; npu) operation=inference.npu.run ;;
        *) nt_fail "Backend must be auto, cpu, vulkan, or npu."; return 2 ;; esac
      [ "$backend" = vulkan ] || [ -z "$device_id" ] || { nt_fail "--device is only valid with --backend vulkan."; return 2; }
      [ -z "$device_id" ] || inference_args+=(--device-id "$device_id")
      if [ -t 0 ]; then
        read -r -p 'Local one-line prompt (max 4096 bytes): ' prompt || return 2
        printf '%s' "$prompt" | python3 "$service" --operation "$operation" --prompt-stdin \
          --max-tokens "$max_tokens" "${inference_args[@]}" --json
      else
        python3 "$service" --operation "$operation" --prompt-stdin \
          --max-tokens "$max_tokens" "${inference_args[@]}" --json
      fi
      ;;
    *) nt_fail "Usage: tx ai {status|devices|npu|runtime|setup|model|run}"; return 2 ;;
  esac
}
