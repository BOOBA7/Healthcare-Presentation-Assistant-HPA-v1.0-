#import <Foundation/Foundation.h>
#import <Vision/Vision.h>
#include <sys/resource.h>
int main() { @autoreleasepool {
 struct rlimit noCore = {0, 0};
 if (setrlimit(RLIMIT_CORE, &noCore) != 0) return 6;
 @try {
 NSData *data = [[NSFileHandle fileHandleWithStandardInput] readDataToEndOfFile];
 if (data.length == 0 || data.length > 20 * 1024 * 1024) return 7;
 VNImageRequestHandler *handler = [[VNImageRequestHandler alloc] initWithData:data options:@{}];
 VNRecognizeTextRequest *ocr = [VNRecognizeTextRequest new];
 ocr.revision = 1; ocr.recognitionLevel = VNRequestTextRecognitionLevelAccurate;
 ocr.recognitionLanguages = @[@"en-US"]; ocr.usesLanguageCorrection = NO; ocr.usesCPUOnly = YES;
 VNDetectFaceRectanglesRequest *face = [VNDetectFaceRectanglesRequest new];
 face.usesCPUOnly = YES; face.revision = 1;
 NSError *error = nil;
 if (![handler performRequests:@[ocr, face] error:&error] || error) return 2;
 if (ocr.results.count > 10000) return 8;
 NSMutableArray *lines = [NSMutableArray new];
 for (VNRecognizedTextObservation *obs in ocr.results) {
  VNRecognizedText *text = [[obs topCandidates:1] firstObject];
  CGRect r = obs.boundingBox;
  if (!text) return 3;
  [lines addObject:@{@"text":text.string, @"confidence":@(text.confidence), @"box":@[@(r.origin.x), @(1-r.origin.y-r.size.height), @(r.origin.x+r.size.width), @(1-r.origin.y)]}];
 }
 NSData *json = [NSJSONSerialization dataWithJSONObject:@{@"lines":lines, @"faces":@(face.results.count)} options:0 error:&error];
 if (!json || error) return 4;
 [[NSFileHandle fileHandleWithStandardOutput] writeData:json];
 } @catch (NSException *e) { return 5; }
} return 0; }
