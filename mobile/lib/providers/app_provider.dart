import 'package:flutter/material.dart';
import 'package:flutter_tts/flutter_tts.dart';
import '../models/video.dart';
import '../models/channel.dart';
import '../services/api_service.dart';

import '../services/notification_service.dart';

class AppProvider with ChangeNotifier {
  final ApiService _apiService = ApiService();
  final FlutterTts _flutterTts = FlutterTts();
  final NotificationService _notificationService = NotificationService();

  List<VideoModel> _videos = [];
  List<ChannelModel> _channels = [];
  bool _isLoading = false;
  bool _isSyncing = false;
  bool _isOnline = true;
  String _serverUrl = '';

  String _selectedCategory = 'All';
  String? _selectedChannelId;
  bool _showBookmarkedOnly = false;
  String _searchQuery = '';

  // TTS State
  bool _isPlayingTts = false;
  String? _currentlySpeakingVideoId;

  List<VideoModel> get videos => _videos;
  List<ChannelModel> get channels => _channels;
  bool get isLoading => _isLoading;
  bool get isSyncing => _isSyncing;
  bool get isOnline => _isOnline;
  String get serverUrl => _serverUrl;

  String get selectedCategory => _selectedCategory;
  String? get selectedChannelId => _selectedChannelId;
  bool get showBookmarkedOnly => _showBookmarkedOnly;
  String get searchQuery => _searchQuery;

  bool get isPlayingTts => _isPlayingTts;
  String? get currentlySpeakingVideoId => _currentlySpeakingVideoId;

  AppProvider() {
    _initTts();
    _notificationService.init();
    loadServerUrl();
    refreshFeed();
    fetchChannels();
  }

  void _initTts() {
    _flutterTts.setStartHandler(() {
      _isPlayingTts = true;
      notifyListeners();
    });
    _flutterTts.setCompletionHandler(() {
      _isPlayingTts = false;
      _currentlySpeakingVideoId = null;
      notifyListeners();
    });
    _flutterTts.setErrorHandler((msg) {
      _isPlayingTts = false;
      _currentlySpeakingVideoId = null;
      notifyListeners();
    });
  }

  Future<void> loadServerUrl() async {
    _serverUrl = await _apiService.getServerUrl();
    notifyListeners();
  }

  Future<void> setServerUrl(String url) async {
    await _apiService.setServerUrl(url);
    _serverUrl = await _apiService.getServerUrl();
    notifyListeners();
    refreshFeed();
    fetchChannels();
  }

  Future<void> refreshFeed() async {
    _isLoading = true;
    notifyListeners();

    try {
      _isOnline = await _apiService.checkHealth();
      final newVideos = await _apiService.getVideos(
        channelId: _selectedChannelId,
        category: _selectedCategory,
        bookmarkedOnly: _showBookmarkedOnly,
        search: _searchQuery,
      );

      if (_videos.isNotEmpty && newVideos.length > _videos.length) {
        final diff = newVideos.length - _videos.length;
        _notificationService.showNotification(
          id: DateTime.now().millisecondsSinceEpoch ~/ 1000,
          title: "📌 SkimTube — Feed Updated",
          body: "$diff new byte-sized video digest${diff > 1 ? 's' : ''} available!",
        );
      }

      _videos = newVideos;
    } catch (e) {
      _isOnline = false;
      _videos = [];
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }

  Future<void> fetchChannels() async {
    try {
      _channels = await _apiService.getChannels();
      notifyListeners();
    } catch (_) {}
  }

  void setCategory(String category) {
    if (_selectedCategory != category) {
      _selectedCategory = category;
      refreshFeed();
    }
  }

  void setChannelFilter(String? channelId) {
    _selectedChannelId = channelId;
    refreshFeed();
  }

  void toggleBookmarkedOnly() {
    _showBookmarkedOnly = !_showBookmarkedOnly;
    refreshFeed();
  }

  void setSearchQuery(String query) {
    _searchQuery = query;
    refreshFeed();
  }

  Future<void> toggleBookmark(VideoModel video) async {
    video.isBookmarked = !video.isBookmarked;
    notifyListeners();

    try {
      await _apiService.toggleBookmark(video.videoId);
    } catch (_) {
      video.isBookmarked = !video.isBookmarked;
      notifyListeners();
    }
  }

  Future<void> addChannel(String channelId, String name) async {
    await _apiService.addChannel(channelId, name);
    await fetchChannels();
    await triggerSync();
  }

  Future<void> deleteChannel(String channelId) async {
    await _apiService.deleteChannel(channelId);
    await fetchChannels();
    refreshFeed();
  }

  Future<void> triggerSync() async {
    _isSyncing = true;
    notifyListeners();

    try {
      await _apiService.triggerSync();
      // Wait a short delay and refresh feed
      await Future.delayed(const Duration(seconds: 3));
      await refreshFeed();
    } catch (_) {
    } finally {
      _isSyncing = false;
      notifyListeners();
    }
  }

  // TTS Audio Player Actions
  Future<void> speakShortSummary(VideoModel video) async {
    if (_isPlayingTts && _currentlySpeakingVideoId == video.videoId) {
      await stopTts();
      return;
    }

    await stopTts();
    _currentlySpeakingVideoId = video.videoId;
    _isPlayingTts = true;
    notifyListeners();

    await _flutterTts.setLanguage("en-US");
    await _flutterTts.setPitch(1.0);
    await _flutterTts.setSpeechRate(0.5);
    await _flutterTts.speak("${video.title}. ${video.shortSummary}");
  }

  Future<void> stopTts() async {
    await _flutterTts.stop();
    _isPlayingTts = false;
    _currentlySpeakingVideoId = null;
    notifyListeners();
  }

  Future<VideoModel> fetchFullVideoDetail(String videoId) async {
    return await _apiService.getVideoDetail(videoId);
  }
}
