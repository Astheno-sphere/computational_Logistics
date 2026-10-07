#[cfg(feature = "ssh-native")]
use super::super::*;
#[cfg(feature = "ssh-native")]
use super::support::service_with_workspaces;

#[cfg(feature = "ssh-native")]
#[test]
fn terminal_channel_output_handles_regular_and_extended_data() {
    let regular = terminal_output_from_channel_message(&russh::ChannelMsg::Data {
        data: Vec::from("stdout").into(),
    });
    let extended = terminal_output_from_channel_message(&russh::ChannelMsg::ExtendedData {
        data: Vec::from("stderr").into(),
        ext: 1,
    });
    let close = terminal_output_from_channel_message(&russh::ChannelMsg::Close);

    assert_eq!(regular.as_deref(), Some("stdout"));
    assert_eq!(extended.as_deref(), Some("stderr"));
    assert!(close.is_none());
}

#[cfg(feature = "ssh-native")]
#[tokio::test]
async fn terminal_output_callback_can_be_registered() {
    let (service, _, _) = service_with_workspaces().await;

    let received = std::sync::Arc::new(std::sync::Mutex::new(Vec::<String>::new()));
    let received_clone = received.clone();

    service.set_terminal_output_callback(std::sync::Arc::new(move |payload| {
        received_clone.lock().unwrap().push(payload);
    }));

    // Verify the callback is stored.
    let has_callback = service
        .on_terminal_output
        .lock()
        .map(|slot| slot.is_some())
        .unwrap_or(false);
    assert!(has_callback, "callback should be registered");

    // Invoke the callback manually and verify the payload.
    if let Ok(slot) = service.on_terminal_output.lock() {
        if let Some(ref cb) = *slot {
            cb(r#"{"sessionId":"test","data":"hello"}"#.to_string());
        }
    }
    let items = received.lock().unwrap();
    assert_eq!(items.len(), 1);
    assert!(items[0].contains("hello"));
}

#[cfg(feature = "ssh-native")]
#[test]
fn native_keepalive_detects_unresponsive_connections_within_about_ten_seconds() {
    let config = native_client_config();
    assert_eq!(
        config.keepalive_interval,
        Some(std::time::Duration::from_secs(3))
    );
    assert_eq!(config.keepalive_max, 2);
    assert_eq!(
        config.keepalive_interval.unwrap().as_secs() * (config.keepalive_max as u64 + 1),
        9
    );
}
