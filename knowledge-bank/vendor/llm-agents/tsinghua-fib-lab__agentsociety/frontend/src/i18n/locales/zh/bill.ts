export default {
    balance: '余额',
    recharge: '充值',
    refresh: '刷新',
    refreshSuccess: '刷新成功',
    autoRefreshOn: '自动刷新已开启',
    autoRefreshOff: '自动刷新已关闭',
    fetchAccountFailed: '获取账户信息失败',
    confirmRecharge: {
        title: '确认充值',
        content: '请确认以下信息：',
        invited: '您是受邀请的用户。',
        testing: '您了解该系统目前仍处于测试阶段，尚未正式运行。',
        incomplete: '您了解系统各项功能可能存在不完善的情况。',
        changeable: '您理解本系统的用途，并了解系统功能、收费标准随时可能变更且不作通知。',
        okText: '确认',
        cancelText: '取消'
    },
    payment: {
        title: '支付',
        instruction: '请在新打开的支付页面完成支付',
        openPayment: '打开支付页面',
        waiting: '等待支付完成...',
        success: '支付成功',
        failed: '支付失败',
        timeout: '支付超时',
        checkFailed: '检查支付状态失败',
        createFailed: '创建支付订单失败',
        alipayOnly: '本平台支付目前仅支持支付宝',
        refundInvoice: '退款与发票开具功能正在开发中，如有需要请联系平台工作人员',
        billingItems: '计费项目目前包括大模型输入Token（3元/百万Token）、输出Token（3元/百万Token）、运行时长（0.001元/秒）'
    },
    table: {
        title: '账单详情',
        id: 'ID',
        item: '项目',
        related_exp_id: '关联实验ID',
        amount: '金额 (元)',
        unit_price: '单价 (元)',
        quantity: '数量',
        description: '描述',
        createdAt: '创建时间',
        updatedAt: '更新时间',
        llm_input_token: 'LLM输入Token（百万Token）',
        llm_output_token: 'LLM输出Token（百万Token）',
        run_time: '运行时间（秒）',
        recharge: '充值'
    }
}; 