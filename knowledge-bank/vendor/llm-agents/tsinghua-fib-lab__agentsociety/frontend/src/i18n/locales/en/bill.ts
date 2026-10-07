export default {
    balance: 'Balance',
    recharge: 'Recharge',
    refresh: 'Refresh',
    refreshSuccess: 'Refresh success',
    autoRefreshOn: 'Auto refresh enabled',
    autoRefreshOff: 'Auto refresh disabled',
    fetchAccountFailed: 'Failed to fetch account information',
    confirmRecharge: {
        title: 'Confirm Recharge',
        content: 'Please confirm the following information:',
        invited: 'You are an invited user.',
        testing: 'You understand that the system is still in testing phase and not officially launched.',
        incomplete: 'You understand that system features may be incomplete.',
        changeable: 'You understand that system features and pricing may change without notice.',
        okText: 'Confirm',
        cancelText: 'Cancel'
    },
    payment: {
        title: 'Payment',
        instruction: 'Please complete the payment on the new opened payment page',
        openPayment: 'Open Payment Page',
        waiting: 'Waiting for payment completion...',
        success: 'Payment Success',
        failed: 'Payment Failed',
        timeout: 'Payment Timeout',
        checkFailed: 'Check Payment Status Failed',
        createFailed: 'Create Payment Order Failed',
        alipayOnly: 'Currently only Alipay payment is supported',
        refundInvoice: 'Refund and invoice functions are under development. Please contact platform staff if needed',
        billingItems: 'Billing items include LLM input tokens (¥3/million tokens), output tokens (¥3/million tokens), and runtime (¥0.001/second)'
    },
    table: {
        title: 'Bill Details',
        id: 'ID',
        item: 'Item',
        related_exp_id: 'Related Experiment ID',
        amount: 'Amount (CNY)',
        unit_price: 'Unit Price (CNY)',
        quantity: 'Quantity',
        description: 'Description',
        createdAt: 'Created At',
        updatedAt: 'Updated At',
        llm_input_token: 'LLM Input Token (million tokens)',
        llm_output_token: 'LLM Output Token (million tokens)',
        run_time: 'Run Time (seconds)',
        recharge: 'Recharge'
    }
}; 