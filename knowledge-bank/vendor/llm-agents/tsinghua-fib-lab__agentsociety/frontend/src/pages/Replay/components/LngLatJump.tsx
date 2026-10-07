import { useState } from "react";
import { Button, Input, Popover, Row, Space, Tooltip } from "antd";
import { LngLat } from "./type";
import React from "react";
import { EnvironmentOutlined } from "@ant-design/icons";

const LngLatJump = (props: {
    onFlyTo: (location: LngLat) => void;
}) => {
    const [lng, setLng] = useState<number | undefined>(undefined);
    const [lat, setLat] = useState<number | undefined>(undefined);

    const handleConfirm = () => {
        if (lng !== undefined && lat !== undefined) {
            props.onFlyTo({ lng, lat });
        }
    };

    const lnglatInput = <Row justify='center' align='middle'>
        <Space>
            <Input
                placeholder="Longitude"
                onChange={(e) => setLng(parseFloat(e.target.value))}
                style={{ width: 200 }}
            />
            <Input
                placeholder="Latitude"
                onChange={(e) => setLat(parseFloat(e.target.value))}
                style={{ width: 200 }}
            />
            <Button onClick={handleConfirm} type='primary'>
                Fly To
            </Button>
        </Space>
    </Row>

    return (<>
        <Tooltip title="Fly to: click to open the input box">
            <Popover placement='bottom' content={lnglatInput} trigger="click">
                <Button icon={<EnvironmentOutlined />} type='text' />
            </Popover>
        </Tooltip>
    </>)
};

export default LngLatJump;