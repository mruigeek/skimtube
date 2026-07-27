import 'dart:convert';
import 'dart:io';
import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';
import '../models/video.dart';
import '../models/channel.dart';

class ApiService {
  static const String _serverUrlKey = 'backend_server_url';
  
  // Default server URLs based on platform
  static String get defaultServerUrl {
    if (!kIsWeb && Platform.isAndroid) {
      return 'http://10.0.2.2:8000';
    }
    return 'http://localhost:8000';
  }


  Future<String> getServerUrl() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getString(_serverUrlKey) ?? defaultServerUrl;
  }

  Future<void> setServerUrl(String url) async {
    final prefs = await SharedPreferences.getInstance();
    String formattedUrl = url.trim();
    if (formattedUrl.endsWith('/')) {
      formattedUrl = formattedUrl.substring(0, formattedUrl.length - 1);
    }
    await prefs.setString(_serverUrlKey, formattedUrl);
  }

  Future<bool> checkHealth() async {
    try {
      final baseUrl = await getServerUrl();
      final response = await http.get(Uri.parse('$baseUrl/api/health')).timeout(const Duration(seconds: 4));
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        return data['status'] == 'online';
      }
    } catch (_) {}
    return false;
  }

  Future<List<VideoModel>> getVideos({
    String? channelId,
    String? category,
    bool bookmarkedOnly = false,
    String? search,
  }) async {
    final baseUrl = await getServerUrl();
    final queryParams = <String, String>{};
    if (channelId != null && channelId.isNotEmpty) queryParams['channel_id'] = channelId;
    if (category != null && category.isNotEmpty && category != 'All') queryParams['category'] = category;
    if (bookmarkedOnly) queryParams['bookmarked_only'] = 'true';
    if (search != null && search.isNotEmpty) queryParams['search'] = search;

    final uri = Uri.parse('$baseUrl/api/videos').replace(queryParameters: queryParams);
    final response = await http.get(uri).timeout(const Duration(seconds: 10));

    if (response.statusCode == 200) {
      final List<dynamic> list = jsonDecode(response.body);
      return list.map((json) => VideoModel.fromJson(json)).toList();
    } else {
      throw Exception('Failed to fetch videos: ${response.statusCode}');
    }
  }

  Future<VideoModel> getVideoDetail(String videoId) async {
    final baseUrl = await getServerUrl();
    final uri = Uri.parse('$baseUrl/api/videos/$videoId');
    final response = await http.get(uri).timeout(const Duration(seconds: 10));

    if (response.statusCode == 200) {
      return VideoModel.fromJson(jsonDecode(response.body));
    } else {
      throw Exception('Failed to fetch video details: ${response.statusCode}');
    }
  }

  Future<bool> toggleBookmark(String videoId) async {
    final baseUrl = await getServerUrl();
    final uri = Uri.parse('$baseUrl/api/videos/$videoId/bookmark');
    final response = await http.post(uri).timeout(const Duration(seconds: 5));

    if (response.statusCode == 200) {
      final data = jsonDecode(response.body);
      return data['is_bookmarked'] ?? false;
    }
    return false;
  }

  Future<List<ChannelModel>> getChannels() async {
    final baseUrl = await getServerUrl();
    final uri = Uri.parse('$baseUrl/api/channels');
    final response = await http.get(uri).timeout(const Duration(seconds: 10));

    if (response.statusCode == 200) {
      final List<dynamic> list = jsonDecode(response.body);
      return list.map((json) => ChannelModel.fromJson(json)).toList();
    } else {
      throw Exception('Failed to fetch channels');
    }
  }

  Future<ChannelModel> addChannel(String channelId, String name) async {
    final baseUrl = await getServerUrl();
    final uri = Uri.parse('$baseUrl/api/channels');
    final response = await http.post(
      uri,
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'channel_id': channelId, 'name': name}),
    ).timeout(const Duration(seconds: 10));

    if (response.statusCode == 200) {
      return ChannelModel.fromJson(jsonDecode(response.body));
    } else {
      final data = jsonDecode(response.body);
      throw Exception(data['detail'] ?? 'Failed to add channel');
    }
  }

  Future<void> deleteChannel(String channelId) async {
    final baseUrl = await getServerUrl();
    final uri = Uri.parse('$baseUrl/api/channels/$channelId');
    final response = await http.delete(uri).timeout(const Duration(seconds: 10));

    if (response.statusCode != 200) {
      throw Exception('Failed to delete channel');
    }
  }

  Future<void> triggerSync() async {
    final baseUrl = await getServerUrl();
    final uri = Uri.parse('$baseUrl/api/sync');
    await http.post(uri).timeout(const Duration(seconds: 5));
  }
}
