import { Typography, List, Flex, Tooltip, Divider, Button } from 'antd';
import { CloseOutlined } from '@ant-design/icons';
import { AgentStatus } from './components/type';
import { useContext } from 'react';
import { parseT } from '../../components/util';
import { StoreContext } from './store';
import { observer } from 'mobx-react-lite';
import { useTranslation } from 'react-i18next';

const { Title } = Typography;
// const IconFont = createFromIconfontCN({
//     scriptUrl: "//at.alicdn.com/t/font_3397267_ttijnd1yjxq.js",
// });

const InfoPanel = observer(() => {
    const store = useContext(StoreContext);
    const { t } = useTranslation();

    const agent = store.clickedAgent;
    const agentStatuses = store.clickedAgentStatuses;

    // 获取翻译的key值，如果没有翻译则使用原始值
    const getTranslatedKey = (key: string) => {
        const translationKey = `replay.infoPanel.${key}`;
        const translated = t(translationKey);
        // 如果翻译结果等于翻译键，说明没有找到翻译，返回原始值
        return translated === translationKey ? key : translated;
    };

    const renderItem = (item: AgentStatus, _index: number) => (
        <Flex className='left-info-history-card'>
            <Flex vertical justify='flex-start' className='left-info-history-inner'>
                <strong>{t('replay.day', { day: item.day })} {parseT(item.t)}</strong>
                <span>{item.action}</span>
                {/* <Flex wrap justify="left">
                    {Object.entries(item.status).map(([k, v]) => (
                        <Flex className='left-info-block' justify='space-between' key={k}>
                            <span style={{ fontWeight: 400, color: "#909399" }}>{k}:&nbsp;&nbsp;</span>
                            <span style={{ fontWeight: 600, color: "#007AFF" }}>{v}</span>
                        </Flex>
                    ))}
                </Flex> */}
            </Flex>
        </Flex>
    );

    const agentName = agent ? agent.name != "" ? agent?.name : t('replay.infoPanel.unknown') : t('replay.infoPanel.chooseAgent');


    const rootClass = agent ? "left-inner" : "left-inner collapsed";

    return (
        <Flex vertical justify='flex-start' align='center' className={rootClass}>
            <Flex gap='small' align='center' style={{ marginTop: "8px" }}>
                <img src="/icon/info.png" width="32px" height="32px" />
                <Title level={4}>{t('replay.infoPanel.title')}</Title>
                <Button
                    shape="circle"
                    icon={<CloseOutlined />}
                    size='small'
                    type='text'
                    onClick={() => { store.setClickedAgentID(undefined) }}
                />
            </Flex>
            <Flex wrap justify="left">
                <Flex className='left-info-block' justify='space-between' key='name'>
                    <span style={{ fontWeight: 400, color: "#909399" }}>{t('replay.infoPanel.name')}:&nbsp;&nbsp;</span>
                    <Tooltip title={<span>{t('replay.infoPanel.id')} = {agent?.id}</span>} >
                        <span style={{ fontWeight: 600, color: "#007AFF" }}>{agentName}</span>
                    </Tooltip>
                </Flex>
                {agent && agent.profile && Object.entries(agent.profile).map(([k, v]) => (
                    <Flex className={k === 'background_story' ? 'left-info-block-status' : 'left-info-block'} justify='space-between' key={k}>
                        <span style={{ fontWeight: 400, color: "#909399" }}>{getTranslatedKey(k)}:&nbsp;&nbsp;</span>
                        <Tooltip title={<span>{v}</span>}>
                            <span style={{ fontWeight: 600, color: "#007AFF", overflow: 'hidden', textOverflow: 'ellipsis', maxWidth: '70%', display: '-webkit-box', WebkitLineClamp: 3, WebkitBoxOrient: 'vertical', lineHeight: '1.2em' }}>{v}</span>
                        </Tooltip>
                    </Flex>
                ))}
            </Flex>
            <Divider />
            <Flex gap='small' align='center'>
                <img src="/icon/status.png" width="32px" height="32px" />
                <Title level={4}>{t('replay.infoPanel.currentStatus')}</Title>
            </Flex>
            {agent && <Flex wrap justify="left" className="w-full">
                <Flex vertical className="w-full">
                    <strong>{t('replay.day', { day: agent.day })} {parseT(agent.t)}</strong>
                    <span>{agent.action}</span>
                    <Flex wrap justify="left">
                        {agent.status && (typeof agent.status === 'string' ? (
                            <Flex className='left-info-block-status' justify='space-between'>
                                <span style={{ fontWeight: 600, color: "#007AFF" }}>{agent.status}</span>
                            </Flex>
                        ) : (
                            Object.entries(agent.status).map(([k, v]) => (
                                <Tooltip title={t('replay.infoPanel.showAsHeatmap')} key={k}>
                                    <Flex className={store.heatmapKeyInStatus === k ? 'left-info-block selected' : 'left-info-block'} justify='space-between' key={k} onClick={() => {
                                        if (typeof v !== "number") {
                                            return;
                                        }
                                        if (store.heatmapKeyInStatus === k) {
                                            store.setHeatmapKeyInStatus(undefined);
                                            return;
                                        }
                                        store.setHeatmapKeyInStatus(k);
                                    }}>
                                        <span style={{ fontWeight: 400, color: "#909399" }}>{getTranslatedKey(k)}:&nbsp;&nbsp;</span>
                                        <span style={{ fontWeight: 600, color: "#007AFF" }}>{v}</span>
                                    </Flex>
                                </Tooltip>
                            ))
                        ))}
                    </Flex>
                </Flex>
            </Flex>}
            <Divider />
            <Flex gap='small' align='center'>
                <img src="/icon/history.png" width="32px" height="32px" />
                <Title level={4}>{t('replay.infoPanel.statusHistory')}</Title>
            </Flex>
            <Flex
                vertical
                className="w-full"
            >
                <List
                    split={false}
                    dataSource={agentStatuses.slice().reverse()}
                    renderItem={renderItem}
                />
            </Flex>
        </Flex>
    );
});

export default InfoPanel;