"""
AIOps 智能运维接口
"""

import json
from fastapi import APIRouter
from sse_starlette.sse import EventSourceResponse
from loguru import logger


from app.models.aiops import AIOpsRequest, MultiAIOpsRequest
from app.services.aiops_service import aiops_service
from app.agent.multi_aiops.supervisor import run_multi_aiops_diagnosis

router = APIRouter()


@router.post("/aiops")
async def diagnose_stream(request: AIOpsRequest):
    """
    AIOps 故障诊断接口（流式 SSE）

    **功能说明：**
    - 自动获取当前系统的活动告警
    - 使用 Plan-Execute-Replan 模式进行智能诊断
    - 流式返回诊断过程和结果

    **SSE 事件类型：**

    1. `status` - 状态更新
       ```json
       {
         "type": "status",
         "stage": "fetching_alerts",
         "message": "正在获取系统告警信息..."
       }
       ```

    2. `plan` - 诊断计划制定完成
       ```json
       {
         "type": "plan",
         "stage": "plan_created",
         "message": "诊断计划已制定，共 6 个步骤",
         "target_alert": {...},
         "plan": ["步骤1: ...", "步骤2: ..."]
       }
       ```

    3. `step_complete` - 步骤执行完成
       ```json
       {
         "type": "step_complete",
         "stage": "step_executed",
         "message": "步骤执行完成 (2/6)",
         "current_step": "查询系统日志",
         "result_preview": "...",
         "remaining_steps": 4
       }
       ```

    4. `report` - 最终诊断报告
       ```json
       {
         "type": "report",
         "stage": "final_report",
         "message": "最终诊断报告已生成",
         "report": "# 故障诊断报告\\n...",
         "evidence": {...}
       }
       ```

    5. `complete` - 诊断完成
       ```json
       {
         "type": "complete",
         "stage": "diagnosis_complete",
         "message": "诊断流程完成",
         "diagnosis": {...}
       }
       ```

    6. `error` - 错误信息
       ```json
       {
         "type": "error",
         "stage": "error",
         "message": "诊断过程发生错误: ..."
       }
       ```

    **使用示例：**
    ```bash
    curl -X POST "http://localhost:9900/api/aiops" \\
      -H "Content-Type: application/json" \\
      -d '{"session_id": "session-123"}' \\
      --no-buffer
    ```

    **前端使用示例：**
    ```javascript
    const eventSource = new EventSource('/api/aiops');

    eventSource.onmessage = (event) => {
      const data = JSON.parse(event.data);

      if (data.type === 'plan') {
        console.log('诊断计划:', data.plan);
      } else if (data.type === 'step_complete') {
        console.log('步骤完成:', data.current_step);
      } else if (data.type === 'report') {
        console.log('最终报告:', data.report);
      } else if (data.type === 'complete') {
        console.log('诊断完成');
        eventSource.close();
      }
    };
    ```

    Args:
        request: AIOps 诊断请求

    Returns:
        SSE 事件流
    """
    session_id = request.session_id or "default"
    logger.info(f"[会话 {session_id}] 收到 AIOps 诊断请求（流式）")

    async def event_generator():
        try:
            async for event in aiops_service.diagnose(session_id=session_id):
                # 发送事件
                yield {
                    "event": "message",
                    "data": json.dumps(event, ensure_ascii=False)
                }

                # 如果是完成或错误事件，结束流
                if event.get("type") in ["complete", "error"]:
                    break

            logger.info(f"[会话 {session_id}] AIOps 诊断流式响应完成")

        except Exception as e:
            logger.error(f"[会话 {session_id}] AIOps 诊断流式响应异常: {e}", exc_info=True)
            yield {
                "event": "message",
                "data": json.dumps({
                    "type": "error",
                    "stage": "exception",
                    "message": f"诊断异常: {str(e)}"
                }, ensure_ascii=False)
            }

    return EventSourceResponse(event_generator())


@router.post("/aiops_multi")
async def diagnose_multi_agent(request: MultiAIOpsRequest):
    """
    多 Agent AIOps 诊断接口（非流式）

    流程：
    1. LogAgent 查询日志证据
    2. MetricsAgent 查询指标证据
    3. KnowledgeAgent 检索知识库
    4. RootCauseAgent 判断根因
    5. ReportAgent 生成最终诊断报告
    """
    session_id = request.session_id or "default"

    logger.info(
        f"[会话 {session_id}] 收到多 Agent AIOps 诊断请求: "
        f"question={request.question}, target_service={request.target_service}"
    )

    try:
        state = run_multi_aiops_diagnosis(
            session_id=session_id,
            question=request.question,
            target_service=request.target_service,
        )

        return {
            "code": 200,
            "message": "success",
            "data": {
                "session_id": state.get("session_id"),
                "question": state.get("question"),
                "target_service": state.get("target_service"),
                "current_step": state.get("current_step"),
                "finished": state.get("finished"),
                "log_summary": state.get("log_summary"),
                "metric_summary": state.get("metric_summary"),
                "knowledge_summary": state.get("knowledge_summary"),
                "root_cause": state.get("root_cause"),
                "confidence": state.get("confidence"),
                "remediation": state.get("remediation"),
                "final_report": state.get("final_report"),
                "errors": state.get("errors", []),
            }
        }

    except Exception as e:
        logger.error(f"[会话 {session_id}] 多 Agent AIOps 诊断失败: {e}", exc_info=True)
        return {
            "code": 500,
            "message": f"多 Agent 诊断失败: {str(e)}",
            "data": {}
        }