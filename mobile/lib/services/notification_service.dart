import 'package:flutter/foundation.dart';

class NotificationService {
  static final NotificationService _instance = NotificationService._internal();
  factory NotificationService() => _instance;
  NotificationService._internal();

  bool _initialized = false;
  bool get isInitialized => _initialized;

  Future<void> init() async {
    _initialized = true;
  }

  Future<void> showNotification({
    required int id,
    required String title,
    required String body,
  }) async {
    if (kDebugMode) {
      print("[Notification Bypass] ID: $id, Title: $title, Body: $body");
    }
  }
}
