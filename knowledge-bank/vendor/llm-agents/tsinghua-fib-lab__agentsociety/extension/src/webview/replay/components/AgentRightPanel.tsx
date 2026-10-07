/**
 * Right-side environment panel
 */

import * as React from 'react';
import { Button, Empty, Flex, Modal, Pagination, Spin, Table, Typography } from 'antd';
import { DatabaseOutlined, ReloadOutlined } from '@ant-design/icons';
import { useReplay } from '../store';
import type { ReplayDatasetInfo } from '../types';

const { Title, Text } = Typography;
const ENV_RAW_ROWS_REQUEST_KEY = 'env-raw-rows';

function renderValue(value: any): React.ReactNode {
  if (value === null || value === undefined) {
    return <span style={{ color: 'var(--as-muted-text)' }}>-</span>;
  }
  if (typeof value === 'object') {
    return (
      <pre style={{ margin: 0, whiteSpace: 'pre-wrap', wordBreak: 'break-word', fontSize: '11px' }}>
        {JSON.stringify(value, null, 2)}
      </pre>
    );
  }
  return String(value);
}

function getColumnLabel(dataset: ReplayDatasetInfo, key: string): string {
  return dataset.columns.find((column) => column.column_name === key)?.title || key;
}

export const AgentRightPanel: React.FC = () => {
  const { state, actions, sendMessage } = useReplay();
  const {
    panelSchema,
    envStateRowsAtStep,
    replayDatasetRowsByRequestKey,
    timeline,
    currentStep,
  } = state;
  const envDatasets = panelSchema?.env_state_datasets ?? [];
  const [selectedDataset, setSelectedDataset] = React.useState<ReplayDatasetInfo | null>(null);
  const [currentPage, setCurrentPage] = React.useState(1);
  const [isModalVisible, setIsModalVisible] = React.useState(false);
  const [modalLoading, setModalLoading] = React.useState(false);
  const pageSize = 20;
  const currentStepNumber = timeline[currentStep]?.step;
  const replayDatasetRows = replayDatasetRowsByRequestKey[ENV_RAW_ROWS_REQUEST_KEY] ?? null;

  React.useEffect(() => {
    if (!selectedDataset || !replayDatasetRows || replayDatasetRows.dataset_id !== selectedDataset.dataset_id) {
      return;
    }
    setModalLoading(false);
  }, [replayDatasetRows, selectedDataset]);

  const openRawDataset = React.useCallback((dataset: ReplayDatasetInfo, page: number = 1) => {
    setSelectedDataset(dataset);
    setCurrentPage(page);
    setIsModalVisible(true);
    setModalLoading(true);
    actions.setReplayDatasetRows(ENV_RAW_ROWS_REQUEST_KEY, null);
    sendMessage({
      command: 'fetchReplayDatasetRows',
      requestKey: ENV_RAW_ROWS_REQUEST_KEY,
      datasetId: dataset.dataset_id,
      page,
      pageSize,
      endStep: currentStepNumber,
      descOrder: true,
    });
  }, [actions, currentStepNumber, sendMessage]);

  const columns = React.useMemo(() => {
    if (!replayDatasetRows || !selectedDataset) {
      return [];
    }
    return replayDatasetRows.columns.map((column) => ({
      title: getColumnLabel(selectedDataset, column),
      dataIndex: column,
      key: column,
      render: (value: any) => renderValue(value),
      ellipsis: true,
      width: 180,
    }));
  }, [replayDatasetRows, selectedDataset]);

  return (
    <Flex vertical className="right-inner" style={{ padding: '12px' }}>
      <Flex align="center" justify="space-between" style={{ marginBottom: '12px' }}>
        <Title level={4} style={{ margin: 0 }}>Environment State</Title>
        {currentStepNumber !== undefined && (
          <Text type="secondary">Step {currentStepNumber}</Text>
        )}
      </Flex>

      <div className="right-content" style={{ padding: 0 }}>
        {envDatasets.length === 0 ? (
          <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description="No env_state datasets exported by this replay"
          />
        ) : (
          envDatasets.map((dataset) => {
            const row = envStateRowsAtStep[dataset.dataset_id]?.row ?? null;
            const entries = row
              ? Object.entries(row).filter(([key]) => !['step', 't'].includes(key))
              : [];

            return (
              <div key={dataset.dataset_id} className="right-card" style={{ marginBottom: '12px' }}>
                <Flex align="center" justify="space-between" style={{ marginBottom: '8px' }}>
                  <div>
                    <div style={{ fontWeight: 600, color: 'var(--as-accent-text)' }}>
                      {dataset.title || dataset.dataset_id}
                    </div>
                    <div className="right-card-meta">
                      {dataset.module_name} / {dataset.dataset_id}
                    </div>
                  </div>
                  <Button
                    size="small"
                    icon={<DatabaseOutlined />}
                    onClick={() => openRawDataset(dataset)}
                  >
                    Raw
                  </Button>
                </Flex>

                {dataset.description ? (
                  <div style={{ fontSize: '12px', color: 'var(--vscode-descriptionForeground)', marginBottom: '8px' }}>
                    {dataset.description}
                  </div>
                ) : null}

                {!row ? (
                  <div className="right-empty">No row at current step</div>
                ) : (
                  <Flex vertical gap={8}>
                    <div style={{ fontSize: '11px', color: 'var(--as-muted-text)' }}>
                      Step {String(row.step ?? '-')} · {row.t ? new Date(String(row.t)).toLocaleString() : 'No timestamp'}
                    </div>
                    {entries.length === 0 ? (
                      <div className="right-empty">No environment fields in this row</div>
                    ) : (
                      entries.map(([key, value]) => (
                        <div key={key} className="right-info-card">
                          <div style={{ fontSize: '11px', color: 'var(--as-muted-text)', marginBottom: '4px' }}>
                            {getColumnLabel(dataset, key)}
                          </div>
                          <div className="right-card-content">{renderValue(value)}</div>
                        </div>
                      ))
                    )}
                  </Flex>
                )}
              </div>
            );
          })
        )}
      </div>

      <Modal
        title={selectedDataset ? `Raw Dataset · ${selectedDataset.title || selectedDataset.dataset_id}` : 'Raw Dataset'}
        open={isModalVisible}
        onCancel={() => setIsModalVisible(false)}
        footer={null}
        width={1000}
        style={{ top: 20 }}
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {selectedDataset && replayDatasetRows?.dataset_id === selectedDataset.dataset_id ? (
            <>
              <Table
                dataSource={replayDatasetRows.rows}
                columns={columns}
                size="small"
                pagination={false}
                scroll={{ x: 'max-content', y: 560 }}
                rowKey={(_, index) => `${selectedDataset.dataset_id}-${index ?? 0}`}
                bordered
              />
              <Flex justify="space-between" align="center">
                <Button
                  icon={<ReloadOutlined />}
                  onClick={() => openRawDataset(selectedDataset, currentPage)}
                >
                  Refresh
                </Button>
                <Pagination
                  simple
                  current={currentPage}
                  total={replayDatasetRows.total}
                  pageSize={pageSize}
                  onChange={(page) => openRawDataset(selectedDataset, page)}
                  size="small"
                />
              </Flex>
            </>
          ) : (
            <div style={{ textAlign: 'center', padding: 40 }}>
              {modalLoading ? <Spin tip="Loading raw rows..." /> : 'Waiting for dataset rows...'}
            </div>
          )}
        </div>
      </Modal>
    </Flex>
  );
};
