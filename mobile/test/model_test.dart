import 'package:flutter_test/flutter_test.dart';
import 'package:skimtube/models/video.dart';
import 'package:skimtube/models/channel.dart';

void main() {
  group('VideoModel Tests', () {
    test('VideoModel.fromJson parses correctly', () {
      final json = {
        'id': 123,
        'video_id': 'dQw4w9WgXcQ',
        'channel_id': 'ch123',
        'channel_name': 'Tech Channel',
        'title': 'Test Video Title',
        'published_at': '2026-07-31T12:00:00Z',
        'short_summary': 'This is a short summary.',
        'content_type': 'tech',
        'thumbnail_url': 'https://img.youtube.com/vi/dQw4w9WgXcQ/hqdefault.jpg',
        'is_bookmarked': true,
      };

      final video = VideoModel.fromJson(json);

      expect(video.id, 123);
      expect(video.videoId, 'dQw4w9WgXcQ');
      expect(video.channelName, 'Tech Channel');
      expect(video.title, 'Test Video Title');
      expect(video.shortSummary, 'This is a short summary.');
      expect(video.isBookmarked, true);
    });

    test('VideoModel instantiation and defaults work', () {
      final video = VideoModel(
        id: 123,
        videoId: 'dQw4w9WgXcQ',
        channelId: 'ch123',
        channelName: 'Tech Channel',
        title: 'Test Video Title',
        publishedAt: '2026-07-31T12:00:00Z',
        shortSummary: 'This is a short summary.',
        contentType: 'tech',
        thumbnailUrl: 'https://img.youtube.com/vi/dQw4w9WgXcQ/hqdefault.jpg',
        isBookmarked: false,
      );

      expect(video.id, 123);
      expect(video.videoId, 'dQw4w9WgXcQ');
      expect(video.isBookmarked, false);
    });
  });

  group('ChannelModel Tests', () {
    test('ChannelModel.fromJson parses correctly', () {
      final json = {
        'channel_id': 'UC123456789',
        'name': 'Marques Brownlee',
      };

      final channel = ChannelModel.fromJson(json);
      expect(channel.channelId, 'UC123456789');
      expect(channel.name, 'Marques Brownlee');
    });
  });
}
