"""
# Kubernetes

本文件下的内容不采用开源许可，仅供商业版使用。

【商业版】Kubernetes 配置文件。
"""

import asyncio
import base64
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import yaml
from fastapi import HTTPException, status
from kubernetes_asyncio import client, config
from kubernetes_asyncio.client.api_client import ApiClient

from ...logger import get_logger

__all__ = ["KubernetesExecutor"]


class KubernetesExecutor:
    def __init__(self, kube_config_search_paths: list[str]):
        self.kube_config_search_paths = kube_config_search_paths
        self._config_loaded = False

    async def _ensure_config_loaded(self):
        """
        确保 Kubernetes 配置已加载
        """
        if self._config_loaded:
            return
            
        """
        加载 Kubernetes 配置，按照incluster, ~/.kube/config, 和 search_paths 的顺序搜索。

        Args:
            search_paths (list[str]): 搜索路径列表
        """
        try:
            config.load_incluster_config()
            self._config_loaded = True
            get_logger().info("Loaded Kubernetes config from incluster config")
            return
        except config.ConfigException:
            pass

        try:
            await config.load_kube_config()
            self._config_loaded = True
            get_logger().info("Loaded Kubernetes config from ~/.kube/config")
            return
        except config.ConfigException:
            pass

        for path in self.kube_config_search_paths:
            if os.path.exists(path):
                await config.load_kube_config(path)
                self._config_loaded = True
                get_logger().info(f"Loaded Kubernetes config from {path}")
                return

        raise config.ConfigException("Failed to load Kubernetes config")

    async def create(
        self,
        config_base64: Optional[str] = None,
        config_path: Optional[str] = None,
        callback_url: str = "",
        callback_auth_token: str = "",
        tenant_id: str = "",
    ):
        # 确保配置已加载
        await self._ensure_config_loaded()

        # Load configuration
        config_dict = None

        # Load configuration from file
        if config_path and not config_base64:
            if not os.path.exists(config_path):
                raise ValueError(f"Configuration file {config_path} does not exist")

            file_ext = Path(config_path).suffix.lower()
            if file_ext == ".json":
                with open(config_path, "r", encoding="utf-8") as f:
                    config_dict = json.load(f)
            elif file_ext in [".yaml", ".yml"]:
                with open(config_path, "r", encoding="utf-8") as f:
                    config_dict = yaml.safe_load(f)
            else:
                raise ValueError(f"Unsupported configuration file format: {file_ext}")

        # Load configuration from base64
        elif config_base64:
            try:
                config_dict = json.loads(base64.b64decode(config_base64).decode())
            except Exception as e:
                raise ValueError(f"Failed to decode base64 configuration: {e}")

        # Ensure configuration exists
        if not config_dict:
            raise ValueError("No configuration provided")

        exp_id = config_dict["exp"]["id"]
        # 生成唯一的 Pod 名称
        pod_name = f"agentsociety-{exp_id}-{datetime.now().strftime('%Y%m%d%H%M%S')}"

        # 如果没有提供 config_base64，则从 config_dict 生成
        if not config_base64 and config_dict:
            container_config_base64 = base64.b64encode(
                json.dumps(config_dict).encode()
            ).decode()
        else:
            container_config_base64 = config_base64
        assert container_config_base64 is not None

        async with ApiClient() as api:
            v1 = client.CoreV1Api(api)

            # 创建 Pod
            pod = client.V1Pod(
                metadata=client.V1ObjectMeta(
                    name=pod_name,
                    namespace="agentsociety",
                    labels={
                        "app": "agentsociety",
                        # for filter when get pod logs or delete pod
                        "agentsociety.fiblab.net/tenant-id": tenant_id,
                        "agentsociety.fiblab.net/exp-id": exp_id,
                        "virtual-kubelet.io/burst-to-cci": "enforce",  # 将 Pod 调度到 CCI
                    },
                ),
                spec=client.V1PodSpec(
                    containers=[
                        client.V1Container(
                            name="runner",
                            image="swr.cn-north-4.myhuaweicloud.com/tsinghua-fib-lab/agentsociety:main",
                            image_pull_policy="Always",
                            command=[
                                "agentsociety",
                                "run",
                                "--config-base64",
                                container_config_base64,
                                "--tenant-id",
                                tenant_id,
                                "--callback-url",
                                f"{callback_url}/api/run-experiments/{exp_id}/finish?callback_auth_token={callback_auth_token}",
                            ],
                            # 添加资源请求和限制
                            resources=client.V1ResourceRequirements(
                                requests={
                                    "cpu": "8",
                                    "memory": "32Gi",
                                },
                                limits={
                                    "cpu": "8",
                                    "memory": "32Gi",
                                },
                            ),
                        )
                    ],
                    restart_policy="Never",
                    host_network=False,
                ),
            )

            # 创建 Pod
            await v1.create_namespaced_pod(namespace="agentsociety", body=pod)  # type: ignore
            get_logger().info(f"Created pod: {pod_name}")

    async def delete(self, tenant_id: str, exp_id: str) -> None:
        """Delete experiment pod in kubernetes using labels and wait until it's gone

        Args:
            tenant_id: Tenant ID
            exp_id: Experiment ID

        Raises:
            HTTPException: If pod not found or deletion timeout
        """
        # 确保配置已加载
        await self._ensure_config_loaded()
        
        async with ApiClient() as api:
            v1 = client.CoreV1Api(api)
            namespace = "agentsociety"

            label_selector = (
                f"agentsociety.fiblab.net/tenant-id={tenant_id},"
                f"agentsociety.fiblab.net/exp-id={exp_id}"
            )

            # 先获取符合条件的pod列表
            pods = await v1.list_namespaced_pod(
                namespace=namespace, label_selector=label_selector
            )

            if not pods.items or len(pods.items) == 0:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Experiment is not running",
                )

            # 删除找到的pod
            for pod in pods.items:
                await v1.delete_namespaced_pod(
                    name=pod.metadata.name,
                    namespace=namespace,
                    body=client.V1DeleteOptions(
                        propagation_policy="Foreground", grace_period_seconds=5
                    ),
                )

            # 等待pod被完全删除
            timeout = datetime.now() + timedelta(minutes=2)  # 2分钟超时
            while datetime.now() < timeout:
                try:
                    pods = await v1.list_namespaced_pod(
                        namespace=namespace, label_selector=label_selector
                    )
                    if not pods.items:
                        return  # Pod已经被完全删除
                    await asyncio.sleep(1)  # 每1秒检查一次
                except Exception as e:
                    get_logger().error(f"Error checking pod status: {e}")

            # 如果超时还没删除完成
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Timeout waiting for pod deletion",
            )

    async def get_logs(self, tenant_id: str, exp_id: str) -> str:
        """Get experiment pod logs from kubernetes using labels

        Args:
            tenant_id: Tenant ID
            exp_id: Experiment ID

        Returns:
            str: Pod logs

        Raises:
            Exception: If failed to get pod logs
        """
        # 确保配置已加载
        await self._ensure_config_loaded()
        
        async with ApiClient() as api:
            v1 = client.CoreV1Api(api)
            namespace = "agentsociety"  # 修正为正确的namespace

            # 使用label selector过滤pod
            label_selector = (
                f"agentsociety.fiblab.net/tenant-id={tenant_id},"
                f"agentsociety.fiblab.net/exp-id={exp_id}"
            )

            # 先获取符合条件的pod列表
            pods = await v1.list_namespaced_pod(
                namespace=namespace, label_selector=label_selector
            )

            if not pods.items or len(pods.items) == 0:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Experiment is not running",
                )

            # 获取第一个pod的日志（通常只会有一个pod）
            logs = await v1.read_namespaced_pod_log(
                name=pods.items[0].metadata.name,
                namespace=namespace,
                tail_lines=1000,
            )
            return logs

    async def get_status(self, tenant_id: str, exp_id: str) -> str:
        """Get experiment pod status from kubernetes using labels

        Args:
            tenant_id: Tenant ID
            exp_id: Experiment ID

        Returns:
            str: Pod status

        Raises:
            Exception: If failed to get pod status
        """
        # 确保配置已加载
        await self._ensure_config_loaded()
        
        async with ApiClient() as api:
            v1 = client.CoreV1Api(api)
            namespace = "agentsociety"

            label_selector = (
                f"agentsociety.fiblab.net/tenant-id={tenant_id},"
                f"agentsociety.fiblab.net/exp-id={exp_id}"
            )

            pods = await v1.list_namespaced_pod(
                namespace=namespace, label_selector=label_selector
            )

            if not pods.items or len(pods.items) == 0:
                return "NotRunning"

            return pods.items[0].status.phase
